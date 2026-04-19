"""Theme-aware infinite desk texture utilities for the GM table."""

from __future__ import annotations

from pathlib import Path
from typing import Tuple

from PIL import Image, ImageTk

from modules.helpers import theme_manager

THEME_TEXTURE_FILENAMES = {
    theme_manager.THEME_MEDIEVAL: "medfan-desk.jpg",
    theme_manager.THEME_DEFAULT: "modern-desk.jpg",
    theme_manager.THEME_SF: "scifi-desk.jpg",
}


def resolve_theme_texture_path(theme_key: str | None) -> Path | None:
    """Return the desk texture path for the active theme when available."""
    key = str(theme_key or theme_manager.THEME_DEFAULT).strip().lower()
    if key not in THEME_TEXTURE_FILENAMES:
        key = theme_manager.THEME_DEFAULT
    candidate = Path("assets") / THEME_TEXTURE_FILENAMES[key]
    return candidate if candidate.exists() else None


class InfiniteDeskTexture:
    """Draw and update a repeating desk texture anchored in world-space."""

    def __init__(self, canvas) -> None:
        self.canvas = canvas
        self._base_texture: Image.Image | None = None
        self._tile_cache: dict[Tuple[int, int], ImageTk.PhotoImage] = {}

    def load_theme(self, theme_key: str | None) -> bool:
        """Load the texture for the requested theme."""
        self._base_texture = None
        self._tile_cache.clear()
        texture_path = resolve_theme_texture_path(theme_key)
        if texture_path is None:
            return False
        try:
            image = Image.open(texture_path)
            if image.mode not in {"RGB", "RGBA"}:
                image = image.convert("RGB")
            self._base_texture = image
            return True
        except Exception:
            self._base_texture = None
            return False

    def draw(self, *, width: int, height: int, camera_x: float, camera_y: float, zoom: float) -> bool:
        """Draw tiled texture for the provided viewport/camera."""
        if self._base_texture is None:
            self.canvas.delete("desk_texture")
            return False
        target_w = max(64, int(round(self._base_texture.width * max(0.25, float(zoom)))))
        target_h = max(64, int(round(self._base_texture.height * max(0.25, float(zoom)))))
        key = (target_w, target_h)
        tile = self._tile_cache.get(key)
        if tile is None:
            scaled = self._base_texture.resize((target_w, target_h), Image.Resampling.LANCZOS)
            tile = ImageTk.PhotoImage(scaled)
            self._tile_cache = {key: tile}

        offset_x = -((float(camera_x) * float(zoom)) % target_w)
        offset_y = -((float(camera_y) * float(zoom)) % target_h)
        cols = max(1, (int(width) // target_w) + 3)
        rows = max(1, (int(height) // target_h) + 3)

        self.canvas.delete("desk_texture")
        start_x = int(offset_x) - target_w
        start_y = int(offset_y) - target_h
        for row in range(rows):
            y = start_y + (row * target_h)
            for col in range(cols):
                x = start_x + (col * target_w)
                self.canvas.create_image(x, y, anchor="nw", image=tile, tags=("desk_texture",))
        self.canvas.lower("desk_texture")
        return True
