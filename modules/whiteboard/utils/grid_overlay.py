from typing import Tuple

from PIL import Image, ImageDraw

GRID_TAG = "whiteboard_grid"


class GridOverlay:
    def __init__(self, *, line_color: str = "#e0e0e0"):
        self.line_color = line_color

    def draw_on_canvas(self, canvas, size: Tuple[int, int], grid_size: int) -> None:
        try:
            canvas.delete(GRID_TAG)
        except Exception:
            pass
        width, height = max(1, int(size[0])), max(1, int(size[1]))
        step = max(4, int(grid_size))
        for x in range(0, width, step):
            canvas.create_line(x, 0, x, height, fill=self.line_color, tags=(GRID_TAG,))
        for y in range(0, height, step):
            canvas.create_line(0, y, width, y, fill=self.line_color, tags=(GRID_TAG,))


def draw_grid_on_image(img: Image.Image, grid_size: int, *, line_color: str = "#e0e0e0") -> Image.Image:
    width, height = img.size
    draw = ImageDraw.Draw(img)
    step = max(4, int(grid_size))
    for x in range(0, width, step):
        draw.line([(x, 0), (x, height)], fill=line_color, width=1)
    for y in range(0, height, step):
        draw.line([(0, y), (width, y)], fill=line_color, width=1)
    return img

