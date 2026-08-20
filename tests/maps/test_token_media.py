"""Regression coverage for animated map-token media."""

import time
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

from modules.maps.media import IMAGE, VIDEO, MediaDecodeError, TokenAnimationManager, detect_media_type, load_thumbnail
from modules.maps.media import animation
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
