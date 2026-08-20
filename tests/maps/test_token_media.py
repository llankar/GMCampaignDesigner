"""Regression coverage for animated map-token media."""

import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

from modules.maps.media import (
    IMAGE,
    VIDEO,
    MediaDecodeError,
    TokenAnimationManager,
    VideoDecoder,
    detect_media_type,
    load_thumbnail,
    replace_token_media,
)
from modules.maps.media import animation
from modules.maps.media import replacement
from modules.maps.views.web_display_view import _describe_remote_tokens
from modules.maps.world_map_view import WorldMapPanel


class FakeWidget:
    def __init__(self):
        self.jobs = {}
        self.cancelled = []
        self.counter = 0

    def after(self, _delay, callback):
        self.counter += 1
        self.jobs[self.counter] = callback
        return self.counter

    def after_cancel(self, job):
        self.cancelled.append(job)
        self.jobs.pop(job, None)

    def run_next(self):
        _, callback = self.jobs.popitem()
        callback()


class FakeDecoder:
    instances = []

    def __init__(self, path, max_size=256):
        if path == "invalid.mp4":
            raise MediaDecodeError("invalid")
        self.closed = False
        self.counter = 0
        self.instances.append(self)

    def read_frame(self):
        self.counter += 1
        return object()

    def close(self):
        self.closed = True


class FakeDecodedFrame:
    def __init__(self, *, fail=False):
        self.requested_format = None
        self.fail = fail

    def reformat(self, *, format):
        self.requested_format = format
        if self.fail:
            raise ValueError("unsupported frame")
        # Include four bytes of padding after each row to verify that the
        # decoder honours PyAV's plane stride rather than assuming tight rows.
        row = bytes((255, 0, 0, 0)) * 4 + bytes((0, 255, 0, 255)) * 4
        plane = FakePlane((row + b"PAD!") * 4)
        plane.line_size = 36
        return SimpleNamespace(width=8, height=4, planes=[plane])


class FakePlane(bytearray):
    pass


def test_video_decoder_requests_rgba_and_preserves_alpha_with_padded_rows():
    decoded_frame = FakeDecodedFrame()
    decoder = VideoDecoder.__new__(VideoDecoder)
    decoder.max_size = 8
    decoder._lock = threading.Lock()
    decoder._closed = False
    decoder._frames = iter([decoded_frame])

    image = decoder.read_frame()

    assert decoded_frame.requested_format == "rgba"
    assert image.mode == "RGBA"
    assert image.size == (8, 4)
    assert image.getpixel((0, 0))[3] == 0
    assert image.getpixel((4, 3)) == (0, 255, 0, 255)


def test_video_decoder_wraps_frame_conversion_errors():
    decoder = VideoDecoder.__new__(VideoDecoder)
    decoder.max_size = 4
    decoder._lock = threading.Lock()
    decoder._closed = False
    decoder._frames = iter([FakeDecodedFrame(fail=True)])

    with pytest.raises(MediaDecodeError, match="Unable to convert video frame"):
        decoder.read_frame()


def test_mp4_selection_and_persisted_hint_detection():
    assert detect_media_type("tokens/hero.MP4") == VIDEO
    assert detect_media_type("tokens/renamed.bin", "video") == VIDEO
    assert detect_media_type("tokens/hero.png") == IMAGE


def test_remote_description_exposes_authenticated_media_metadata():
    owner = type("Owner", (), {})()
    owner.zoom = 1.0
    owner.pan_x = owner.pan_y = 0.0
    owner.base_img = type("Base", (), {"size": (800, 600)})()
    owner.token_size = 48
    owner.tokens = [{
        "type": "token", "entity_type": "PC", "entity_id": "Hero",
        "position": (12, 34), "size": 64, "player_visible": True,
        "image_path": "tokens/hero.mp4", "media_type": "video",
    }]
    payload = _describe_remote_tokens(owner)[0]
    assert payload["media_type"] == VIDEO
    assert payload["media_url"].startswith("/media/token/")


def test_invalid_video_is_rejected_without_crashing(tmp_path):
    with pytest.raises(MediaDecodeError):
        load_thumbnail(str(tmp_path / "missing.mp4"), VIDEO)


def test_animation_loops_and_releases_on_delete_map_change_and_close(monkeypatch):
    FakeDecoder.instances.clear()
    monkeypatch.setattr(animation, "VideoDecoder", FakeDecoder)
    widget = FakeWidget()
    delivered = []
    manager = TokenAnimationManager(widget, lambda token, frame: delivered.append((token, frame)))
    first, copied = {"size": 48}, {"size": 96}
    assert manager.register(first, "hero.mp4")
    assert manager.register(copied, "hero.mp4")

    # The centralized tick submits decoding, and a later tick delivers it.
    widget.run_next()
    deadline = time.monotonic() + 1
    while len(delivered) < 2 and time.monotonic() < deadline:
        if not manager._results.empty() and widget.jobs:
            widget.run_next()
        else:
            time.sleep(0.01)
    assert {id(item[0]) for item in delivered} == {id(first), id(copied)}

    manager.unregister(first)  # token deletion
    deadline = time.monotonic() + 1
    while not FakeDecoder.instances[0].closed and time.monotonic() < deadline:
        time.sleep(0.01)
    assert FakeDecoder.instances[0].closed
    manager.clear()  # map change
    deadline = time.monotonic() + 1
    while not all(decoder.closed for decoder in FakeDecoder.instances) and time.monotonic() < deadline:
        time.sleep(0.01)
    assert all(decoder.closed for decoder in FakeDecoder.instances)
    assert not manager.register({}, "invalid.mp4")
    manager.close()  # window close / after cancellation
    assert manager._closed


@pytest.mark.parametrize("method_name", ["_delete_selected_token", "_delete_token"])
def test_world_map_deletion_unregisters_video_before_removal(method_name):
    token = {"type": "entity", "media_type": VIDEO}
    calls = []
    owner = SimpleNamespace(
        fog_mode=False,
        selected_token=token,
        tokens=[token],
        _token_animation_manager=SimpleNamespace(unregister=lambda item: calls.append(item)),
        _draw_scene=lambda: None,
        _persist_tokens=lambda: None,
        _clear_inspector=lambda: None,
    )

    method = getattr(WorldMapPanel, method_name)
    method(owner, token) if method_name == "_delete_token" else method(owner)

    assert calls == [token]
    assert owner.tokens == []


def test_world_map_persistence_reload_keeps_only_media_metadata():
    runtime_frame = object()
    token = {
        "type": "entity", "entity_type": "PC", "entity_id": "Hero",
        "portrait_path": "tokens/hero.mp4", "media_type": VIDEO,
        "size": 96, "source_image": runtime_frame, "pil_image": runtime_frame,
    }
    entry = {"name": "World"}
    owner = SimpleNamespace(
        current_world_map=entry,
        current_map_name="World",
        tokens=[token],
        world_maps={},
        mask_img=None,
        _save_world_map_store=lambda: None,
        _fetch_record=lambda *_args: None,
        _capture_view_state=lambda: None,
    )

    WorldMapPanel._persist_tokens(owner)
    stored = entry["tokens"][0]
    assert stored["portrait_path"] == "tokens/hero.mp4"
    assert stored["media_type"] == VIDEO
    assert "source_image" not in stored and "pil_image" not in stored

    restored = WorldMapPanel._deserialize_tokens(owner, entry)[0]
    assert restored["media_type"] == VIDEO
    assert restored["size"] == 96


class ReplacementManager:
    def __init__(self, *, register_result=True):
        self.registered = []
        self.unregistered = []
        self.register_result = register_result

    def register(self, token, path):
        self.registered.append((token, path))
        return self.register_result

    def unregister(self, token):
        self.unregistered.append(token)


class ReplacementImage:
    def __init__(self, size=(20, 30)):
        self.size = size

    def resize(self, size, _resampling):
        return ReplacementImage(size)


@pytest.mark.parametrize(
    ("old_type", "new_suffix", "expected_type", "unregisters", "registers"),
    [
        (IMAGE, ".png", IMAGE, 0, 0),
        (IMAGE, ".mp4", VIDEO, 0, 1),
        (VIDEO, ".png", IMAGE, 1, 0),
        (VIDEO, ".mp4", VIDEO, 1, 1),
    ],
)
def test_replace_token_media_all_transitions_preserve_state(
    tmp_path, monkeypatch, old_type, new_suffix, expected_type, unregisters, registers
):
    campaign = tmp_path / "campaign"
    asset = campaign / "tokens" / f"replacement{new_suffix}"
    asset.parent.mkdir(parents=True)
    asset.write_bytes(b"media")
    decoded = ReplacementImage()
    monkeypatch.setattr(replacement.ConfigHelper, "get_campaign_dir", lambda: str(campaign))
    monkeypatch.setattr(replacement, "load_thumbnail", lambda *_args: decoded)
    manager = ReplacementManager()
    persisted = []
    refreshed = []
    token = {
        "type": "token", "image_path": "tokens/original.mp4", "media_type": old_type,
        "position": (12, 34), "size": 72, "border_color": "blue", "hp": 8,
        "player_visible": False, "facing_angle": 135, "entity_id": "Hero",
        "canvas_ids": (11, 12), "source_image": object(), "pil_image": object(),
    }
    controller = SimpleNamespace(
        token_size=48, tokens=[token], _token_animation_manager=manager,
        _ensure_token_animation_manager=lambda: manager,
        _display_token_frame=lambda item, frame: refreshed.append((item, frame)),
        _persist_tokens=lambda: persisted.append(True), _web_server_thread=None,
    )
    retained = {key: token[key] for key in (
        "position", "size", "border_color", "hp", "player_visible", "facing_angle",
        "entity_id", "canvas_ids",
    )}

    result = replace_token_media(controller, token, str(asset))

    assert result.success
    assert token["image_path"] == f"tokens/replacement{new_suffix}"
    assert token["media_type"] == expected_type
    assert token["source_image"] is decoded
    assert token["pil_image"].size == (72, 72)
    assert {key: token[key] for key in retained} == retained
    assert len(manager.unregistered) == unregisters
    assert len(manager.registered) == registers
    assert refreshed == [(token, decoded)]
    assert persisted == [True]


def test_replace_token_media_decode_failure_rolls_back_media_and_animation(tmp_path, monkeypatch):
    selected = tmp_path / "broken.png"
    selected.write_bytes(b"broken")
    monkeypatch.setattr(
        replacement, "load_thumbnail", lambda *_args: (_ for _ in ()).throw(MediaDecodeError("broken"))
    )
    manager = ReplacementManager()
    old_source, old_pil = object(), object()
    token = {
        "type": "token", "image_path": "tokens/original.mp4", "media_type": VIDEO,
        "size": 48, "source_image": old_source, "pil_image": old_pil,
    }
    controller = SimpleNamespace(token_size=48, _token_animation_manager=manager)

    result = replace_token_media(controller, token, str(selected))

    assert not result.success
    assert token["image_path"] == "tokens/original.mp4"
    assert token["media_type"] == VIDEO
    assert token["source_image"] is old_source and token["pil_image"] is old_pil
    assert manager.unregistered == [] and manager.registered == []


def test_replace_token_media_registration_failure_restores_old_video(tmp_path, monkeypatch):
    campaign = tmp_path / "campaign"
    selected = campaign / "tokens" / "new.mp4"
    old_path = campaign / "tokens" / "old.mp4"
    selected.parent.mkdir(parents=True)
    selected.write_bytes(b"new")
    old_path.write_bytes(b"old")
    monkeypatch.setattr(replacement.ConfigHelper, "get_campaign_dir", lambda: str(campaign))
    monkeypatch.setattr(replacement, "load_thumbnail", lambda *_args: ReplacementImage())
    manager = ReplacementManager(register_result=False)
    old_source, old_pil = object(), object()
    token = {
        "type": "token", "image_path": "tokens/old.mp4", "media_type": VIDEO,
        "size": 48, "source_image": old_source, "pil_image": old_pil,
    }
    controller = SimpleNamespace(
        token_size=48, _token_animation_manager=manager,
        _ensure_token_animation_manager=lambda: manager,
    )

    result = replace_token_media(controller, token, str(selected))

    assert not result.success
    assert token["image_path"] == "tokens/old.mp4"
    assert token["media_type"] == VIDEO
    assert token["source_image"] is old_source and token["pil_image"] is old_pil
    assert manager.unregistered == [token, token]
    assert manager.registered == [(token, str(selected)), (token, str(old_path))]


def test_replace_token_media_rejects_unsupported_extension_without_decoding(tmp_path, monkeypatch):
    selected = tmp_path / "token.svg"
    selected.write_text("<svg/>", encoding="utf-8")
    decoded = []
    monkeypatch.setattr(replacement, "load_thumbnail", lambda *_args: decoded.append(True))
    token = {"type": "token", "image_path": "old.png", "media_type": IMAGE}

    result = replace_token_media(SimpleNamespace(), token, str(selected))

    assert not result.success
    assert "supported" in result.error
    assert decoded == []
    assert token == {"type": "token", "image_path": "old.png", "media_type": IMAGE}
