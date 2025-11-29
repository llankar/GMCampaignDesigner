from typing import Tuple

from PIL import Image, ImageDraw

GRID_TAG = "whiteboard_grid"


class GridOverlay:
    def __init__(self, *, line_color: str = "#e0e0e0"):
        self.line_color = line_color

    def draw_on_canvas(self, canvas, size: Tuple[int, int], grid_size: int, *, zoom: float = 1.0, pan: Tuple[float, float] = (0.0, 0.0)) -> None:
        try:
            canvas.delete(GRID_TAG)
        except Exception:
            pass
        width, height = max(1, int(size[0])), max(1, int(size[1]))
        zoom = max(0.05, float(zoom))
        step = max(4, int(grid_size))
        pan_x, pan_y = pan
        width_scaled = width * zoom
        height_scaled = height * zoom
        for x in range(0, width + step, step):
            screen_x = pan_x + x * zoom
            canvas.create_line(screen_x, pan_y, screen_x, pan_y + height_scaled, fill=self.line_color, tags=(GRID_TAG,))
        for y in range(0, height + step, step):
            screen_y = pan_y + y * zoom
            canvas.create_line(pan_x, screen_y, pan_x + width_scaled, screen_y, fill=self.line_color, tags=(GRID_TAG,))


def draw_grid_on_image(img: Image.Image, grid_size: int, *, line_color: str = "#e0e0e0") -> Image.Image:
    width, height = img.size
    draw = ImageDraw.Draw(img)
    step = max(4, int(grid_size))
    for x in range(0, width, step):
        draw.line([(x, 0), (x, height)], fill=line_color, width=1)
    for y in range(0, height, step):
        draw.line([(0, y), (width, y)], fill=line_color, width=1)
    return img

