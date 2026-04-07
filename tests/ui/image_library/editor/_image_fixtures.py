from __future__ import annotations

from PIL import Image


CANVAS_SIZE = (6, 6)


def solid_rgba(color: tuple[int, int, int, int], *, size: tuple[int, int] = CANVAS_SIZE) -> Image.Image:
    """Create a deterministic in-memory RGBA image for editor tests."""
    return Image.new("RGBA", size, color)


def pixel(image: Image.Image, x: int, y: int) -> tuple[int, int, int, int]:
    """Read RGBA pixel as an explicit tuple."""
    return tuple(image.getpixel((x, y)))
