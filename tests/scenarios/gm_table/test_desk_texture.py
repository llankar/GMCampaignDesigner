"""Tests for theme-aware desk texture resolution."""

from __future__ import annotations

from modules.helpers import theme_manager
from modules.scenarios.gm_table.desk_texture import (
    InfiniteDeskTexture,
    resolve_theme_texture_path,
)


class _CanvasStub:
    def __init__(self) -> None:
        self.deleted_tags: list[str] = []

    def delete(self, tag: str) -> None:
        self.deleted_tags.append(tag)


def test_resolve_theme_texture_path_uses_theme_specific_file(tmp_path, monkeypatch):
    """Medieval theme should target medfan desk asset when present."""
    monkeypatch.chdir(tmp_path)
    assets = tmp_path / "assets"
    assets.mkdir()
    expected = assets / "medfan-desk.jpg"
    expected.write_bytes(b"stub")

    resolved = resolve_theme_texture_path(theme_manager.THEME_MEDIEVAL)

    assert resolved is not None
    assert resolved.resolve() == expected.resolve()


def test_resolve_theme_texture_path_falls_back_to_default_theme(tmp_path, monkeypatch):
    """Unknown themes should resolve via the modern desk texture."""
    monkeypatch.chdir(tmp_path)
    assets = tmp_path / "assets"
    assets.mkdir()
    expected = assets / "modern-desk.jpg"
    expected.write_bytes(b"stub")

    resolved = resolve_theme_texture_path("unknown-theme")

    assert resolved is not None
    assert resolved.resolve() == expected.resolve()


def test_infinite_desk_texture_clears_canvas_when_texture_missing():
    """Draw should clear tagged textures when no asset is available."""
    canvas = _CanvasStub()
    renderer = InfiniteDeskTexture(canvas)

    drawn = renderer.draw(width=800, height=600, camera_x=0.0, camera_y=0.0, zoom=1.0)

    assert drawn is False
    assert canvas.deleted_tags == ["desk_texture"]
