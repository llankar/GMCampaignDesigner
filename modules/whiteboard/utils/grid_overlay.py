import math
from typing import Tuple

from PIL import Image, ImageDraw

GRID_TAG = "whiteboard_grid"


class GridOverlay:
    def __init__(self, *, line_color: str = "#e0e0e0"):
        self.line_color = line_color

    def draw_on_canvas(
        self,
        canvas,
        viewport_size: Tuple[int, int],
        grid_size: int,
        *,
        zoom: float = 1.0,
        pan: Tuple[float, float] = (0.0, 0.0),
        origin: Tuple[float, float] = (0.0, 0.0),
    ) -> None:
        try:
            canvas.delete(GRID_TAG)
        except Exception:
            pass
        width, height = max(1, int(viewport_size[0])), max(1, int(viewport_size[1]))
        zoom = max(0.05, float(zoom))
        step = max(4, int(grid_size))
        pan_x, pan_y = pan
        origin_x, origin_y = origin

        view_left = -pan_x / zoom
        view_top = -pan_y / zoom
        view_right = view_left + width / zoom
        view_bottom = view_top + height / zoom

        start_x = math.floor(min(origin_x, view_left) / step) * step
        end_x = math.ceil(max(origin_x + width, view_right) / step) * step
        x = start_x
        while x <= end_x + step:
            screen_x = pan_x + x * zoom
            canvas.create_line(screen_x, 0, screen_x, height, fill=self.line_color, tags=(GRID_TAG,))
            x += step

        start_y = math.floor(min(origin_y, view_top) / step) * step
        end_y = math.ceil(max(origin_y + height, view_bottom) / step) * step
        y = start_y
        while y <= end_y + step:
            screen_y = pan_y + y * zoom
            canvas.create_line(pan_x - width, screen_y, pan_x + width * 2, screen_y, fill=self.line_color, tags=(GRID_TAG,))
            y += step


def draw_grid_on_image(
    img: Image.Image,
    grid_size: int,
    *,
    line_color: str = "#e0e0e0",
    origin: Tuple[float, float] = (0.0, 0.0),
    zoom: float = 1.0,
) -> Image.Image:
    width, height = img.size
    draw = ImageDraw.Draw(img)
    zoom = max(0.05, float(zoom))
    step = max(4, int(grid_size * zoom))
    origin_x, origin_y = origin
    start_x = math.floor(origin_x / grid_size) * grid_size
    end_x = origin_x + width / zoom
    x = start_x
    while x <= end_x + grid_size:
        screen_x = int(round((x - origin_x) * zoom))
        draw.line([(screen_x, 0), (screen_x, height)], fill=line_color, width=1)
        x += grid_size
    start_y = math.floor(origin_y / grid_size) * grid_size
    end_y = origin_y + height / zoom
    y = start_y
    while y <= end_y + grid_size:
        screen_y = int(round((y - origin_y) * zoom))
        draw.line([(0, screen_y), (width, screen_y)], fill=line_color, width=1)
        y += grid_size
    return img

