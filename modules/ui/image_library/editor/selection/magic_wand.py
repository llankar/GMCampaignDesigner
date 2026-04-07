"""Magic-wand region extraction utilities."""

from __future__ import annotations

from collections import deque

from PIL import Image


def _within_tolerance(a: tuple[int, int, int, int], b: tuple[int, int, int, int], tolerance: int) -> bool:
    return abs(a[0] - b[0]) <= tolerance and abs(a[1] - b[1]) <= tolerance and abs(a[2] - b[2]) <= tolerance and abs(a[3] - b[3]) <= tolerance


def magic_select_mask(image: Image.Image, seed_x: int, seed_y: int, tolerance: int) -> Image.Image:
    """Build a connected-region mask from a seed pixel and color tolerance."""
    rgba = image.convert("RGBA")
    width, height = rgba.size
    if seed_x < 0 or seed_y < 0 or seed_x >= width or seed_y >= height:
        return Image.new("L", (width, height), 0)

    pixels = rgba.load()
    mask = Image.new("L", (width, height), 0)
    mask_pixels = mask.load()
    visited = [[False for _ in range(width)] for _ in range(height)]

    seed = pixels[seed_x, seed_y]
    queue: deque[tuple[int, int]] = deque([(seed_x, seed_y)])
    visited[seed_y][seed_x] = True

    while queue:
        x, y = queue.popleft()
        current = pixels[x, y]
        if not _within_tolerance(current, seed, tolerance):
            continue
        mask_pixels[x, y] = 255

        for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if 0 <= nx < width and 0 <= ny < height and not visited[ny][nx]:
                visited[ny][nx] = True
                queue.append((nx, ny))

    return mask
