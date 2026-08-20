"""Unit coverage for media-aware entity reveals."""
from pathlib import Path
import sys
import types

from modules.ui import image_viewer
from modules.ui.entity_media.types import media_type, portrait_filetypes


def test_media_types_include_supported_video_extensions():
    for suffix in (".mp4", ".avi", ".mov", ".mkv", ".webm", ".m4v"):
        assert media_type(f"portrait{suffix}") == "video"
    assert media_type("portrait.PNG") == "image"
    assert media_type("portrait.txt") is None
    assert "*.webm" in portrait_filetypes()[0][1]


def test_video_is_resolved_relative_to_campaign_and_routed(monkeypatch, tmp_path: Path):
    video = tmp_path / "assets" / "portraits" / "hero.mp4"
    video.parent.mkdir(parents=True)
    video.touch()
    calls = []
    fake_player = types.SimpleNamespace(
        stop_active_video=lambda: calls.append(("stop",)),
        play_video_on_second_screen=lambda path, title=None: calls.append((path, title)) or "window",
    )
    monkeypatch.setitem(sys.modules, "modules.ui.video_player", fake_player)
    monkeypatch.setattr(image_viewer.ConfigHelper, "get_campaign_dir", lambda: str(tmp_path))

    result = image_viewer.show_entity_media("assets/portraits/hero.mp4", title="Hero")

    assert result == "window"
    assert calls == [("stop",), (str(video), "Hero")]


def test_unsupported_media_reports_error(monkeypatch, tmp_path: Path):
    media = tmp_path / "portrait.txt"
    media.touch()
    errors = []
    fake_player = types.SimpleNamespace(stop_active_video=lambda: None)
    monkeypatch.setitem(sys.modules, "modules.ui.video_player", fake_player)
    monkeypatch.setattr(image_viewer.ConfigHelper, "get_campaign_dir", lambda: str(tmp_path))
    monkeypatch.setattr(image_viewer.messagebox, "showerror", lambda *args: errors.append(args))

    assert image_viewer.show_entity_media(str(media)) is None
    assert "not supported" in errors[0][1]
