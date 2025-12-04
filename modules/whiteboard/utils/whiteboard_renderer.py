import io
from typing import List, Dict, Tuple, Any

from PIL import Image, ImageDraw

from modules.helpers.logging_helper import log_module_import
from modules.whiteboard.models.layer_types import WhiteboardLayer, normalize_layer
from modules.whiteboard.utils.grid_overlay import draw_grid_on_image
from modules.whiteboard.utils.stamp_assets import load_pil_asset
from modules.maps.utils.text_items import TextFontCache

log_module_import(__name__)

DEFAULT_COLOR = "#FF0000"
DEFAULT_SIZE: Tuple[int, int] = (1920, 1080)


def _resolve_size(size: Tuple[int, int]) -> Tuple[int, int]:
    if not size:
        return DEFAULT_SIZE
    try:
        width, height = int(size[0]), int(size[1])
        if width <= 0 or height <= 0:
            return DEFAULT_SIZE
        return width, height
    except Exception:
        return DEFAULT_SIZE


PLAYER_TEXT_SCALE = 2.0


def render_whiteboard_image(
    items: List[Dict[str, Any]],
    size: Tuple[int, int] = DEFAULT_SIZE,
    *,
    font_cache: TextFontCache | None = None,
    include_text: bool = True,
    grid_enabled: bool = False,
    grid_size: int = 50,
    grid_origin: Tuple[float, float] = (0.0, 0.0),
    for_player: bool = False,
    zoom: float = 1.0,
) -> Image.Image:
    width, height = _resolve_size(size)
    zoom = max(0.05, float(zoom))
    screen_width = max(1, int(width * zoom))
    screen_height = max(1, int(height * zoom))
    base_color = (255, 255, 255, 255)
    img = Image.new("RGBA", (screen_width, screen_height), base_color)
    draw = ImageDraw.Draw(img)

    font_cache = font_cache or TextFontCache()

    def _scale_point(point: Tuple[float, float]) -> Tuple[float, float]:
        return point[0] * zoom, point[1] * zoom

    if grid_enabled:
        draw_grid_on_image(
            img,
            int(max(1, grid_size)),
            origin=grid_origin,
            zoom=zoom,
        )

    for item in items:
        if for_player and normalize_layer(item.get("layer")) == WhiteboardLayer.GM.value:
            continue
        item_type = item.get("type")
        if item_type == "stroke":
            points = item.get("points") or []
            if len(points) < 2:
                continue
            color = item.get("color", DEFAULT_COLOR)
            width_px = int(max(1, float(item.get("width", 4)) * zoom))
            flattened = []
            for x, y in points:
                sx, sy = _scale_point((x, y))
                flattened.extend([sx, sy])
            draw.line(flattened, fill=color, width=width_px, joint="miter")
        elif item_type == "text" and include_text:
            text_value = item.get("text", "")
            pos = item.get("position") or (0, 0)
            color = item.get("color", DEFAULT_COLOR)
            text_scale = PLAYER_TEXT_SCALE if for_player else 1.0
            size_px = int(
                max(1, float(item.get("text_size", item.get("size", 24))) * zoom * text_scale)
            )
            font = font_cache.pil_font(size_px)
            try:
                draw.text(_scale_point(pos), text_value, fill=color, font=font, anchor="lt")
            except Exception:
                draw.text(_scale_point(pos), text_value, fill=color, font=font)
        elif item_type == "stamp":
            asset_path = item.get("asset")
            if not asset_path:
                continue
            pos = item.get("position") or (0, 0)
            size_px = int(max(1, float(item.get("size", 48)) * zoom))
            try:
                stamp_img = load_pil_asset(asset_path, size_px)
                sx, sy = _scale_point(pos)
                img.alpha_composite(stamp_img, dest=(int(sx), int(sy)))
            except Exception:
                continue

    return img.convert("RGB")


def render_png_bytes(items: List[Dict[str, Any]], size: Tuple[int, int] = DEFAULT_SIZE) -> bytes:
    img = render_whiteboard_image(items, size, font_cache=None)
    buffer = io.BytesIO()
    try:
        img.save(buffer, format="PNG")
        return buffer.getvalue()
    finally:
        buffer.close()
