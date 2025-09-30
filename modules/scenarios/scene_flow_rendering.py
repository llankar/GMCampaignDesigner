"""Shared helpers for rendering scene flow canvases."""

from __future__ import annotations

import math
from typing import MutableMapping, Optional, Sequence, Tuple

from PIL import Image, ImageDraw, ImageFilter, ImageTk

SCENE_FLOW_BG = "#1B1F27"
_GRID_TILE_KEY = "__scene_flow_tile__"

ShadowCache = MutableMapping[Tuple[int, int, int, int, int], Tuple[ImageTk.PhotoImage, int]]
TileCache = MutableMapping[str, ImageTk.PhotoImage]


def _resolve_tile(cache: TileCache, canvas, *, cache_key: str = _GRID_TILE_KEY) -> ImageTk.PhotoImage:
    tile = cache.get(cache_key)
    if tile is None:
        tile = create_grid_tile(canvas)
        cache[cache_key] = tile
    return tile


def apply_scene_flow_canvas_styling(
    canvas,
    *,
    tile_cache: TileCache,
    extent_width: int,
    extent_height: int,
    background_tags: Sequence[str] = ("background", "scene_flow_bg"),
    cache_key: str = _GRID_TILE_KEY,
) -> Optional[ImageTk.PhotoImage]:
    """Configure the canvas with the shared grid background used by scene views."""

    if canvas is None:
        return None

    canvas.configure(bg=SCENE_FLOW_BG)
    try:
        canvas.delete("scene_flow_bg")
    except Exception:
        pass

    tile = _resolve_tile(tile_cache, canvas, cache_key=cache_key)
    draw_grid_background(canvas, tile, extent_width, extent_height, background_tags)
    return tile


def draw_grid_background(
    canvas,
    tile: Optional[ImageTk.PhotoImage],
    extent_width: int,
    extent_height: int,
    tags: Sequence[str] = ("background", "scene_flow_bg"),
) -> None:
    """Tile ``tile`` across the canvas within the provided extents."""

    if tile is None or canvas is None:
        return

    tile_width = max(tile.width(), 1)
    tile_height = max(tile.height(), 1)
    cols = max(1, math.ceil(extent_width / tile_width))
    rows = max(1, math.ceil(extent_height / tile_height))

    for i in range(cols):
        for j in range(rows):
            canvas.create_image(
                i * tile_width,
                j * tile_height,
                image=tile,
                anchor="nw",
                tags=tuple(tags),
            )


def create_grid_tile(
    canvas,
    *,
    size: int = 256,
    spacing: int = 96,
    line_color = (255, 255, 255, 25),
    dot_color = (255, 255, 255, 40),
) -> ImageTk.PhotoImage:
    """Create a PhotoImage used for the tiled background grid."""

    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    for offset in range(0, size, spacing):
        draw.line([(offset, 0), (offset, size)], fill=line_color, width=1)
        draw.line([(0, offset), (size, offset)], fill=line_color, width=1)

    dot_radius = 2
    for x in range(0, size, spacing):
        for y in range(0, size, spacing):
            draw.ellipse(
                [
                    x - dot_radius,
                    y - dot_radius,
                    x + dot_radius,
                    y + dot_radius,
                ],
                fill=dot_color,
            )

    return ImageTk.PhotoImage(image, master=canvas)


def get_shadow_image(
    canvas,
    cache: ShadowCache,
    width: int,
    height: int,
    scale: float,
) -> Tuple[Optional[ImageTk.PhotoImage], int]:
    """Return a cached drop shadow sized for the given dimensions."""

    rounded_width = max(10, int(width))
    rounded_height = max(10, int(height))
    blur_radius = max(6, int(10 * scale))
    padding = max(4, int(6 * scale))
    corner_radius = max(16, int(20 * scale))
    offset = blur_radius + padding
    cache_key = (rounded_width, rounded_height, blur_radius, padding, corner_radius)

    cached = cache.get(cache_key)
    if cached:
        return cached

    total_width = rounded_width + 2 * offset
    total_height = rounded_height + 2 * offset

    shadow = Image.new("RGBA", (total_width, total_height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(shadow)
    draw.rounded_rectangle(
        [
            offset,
            offset,
            offset + rounded_width,
            offset + rounded_height,
        ],
        radius=corner_radius,
        fill=(0, 0, 0, 120),
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(radius=blur_radius))
    photo = ImageTk.PhotoImage(shadow, master=canvas)
    cache[cache_key] = (photo, offset)
    return photo, offset


__all__ = [
    "SCENE_FLOW_BG",
    "apply_scene_flow_canvas_styling",
    "create_grid_tile",
    "draw_grid_background",
    "get_shadow_image",
]
