import io
from typing import List, Dict, Tuple, Any

from PIL import Image, ImageDraw

from modules.helpers.logging_helper import log_module_import
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


def render_whiteboard_image(
    items: List[Dict[str, Any]],
    size: Tuple[int, int] = DEFAULT_SIZE,
    *,
    font_cache: TextFontCache | None = None,
) -> Image.Image:
    width, height = _resolve_size(size)
    img = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(img)

    font_cache = font_cache or TextFontCache()

    for item in items:
        item_type = item.get("type")
        if item_type == "stroke":
            points = item.get("points") or []
            if len(points) < 2:
                continue
            color = item.get("color", DEFAULT_COLOR)
            width_px = int(max(1, float(item.get("width", 4))))
            flattened = []
            for x, y in points:
                flattened.extend([x, y])
            draw.line(flattened, fill=color, width=width_px, joint="curve")
        elif item_type == "text":
            text = item.get("text", "")
            pos = item.get("position") or (0, 0)
            color = item.get("color", DEFAULT_COLOR)
            size_px = int(item.get("size", 24))
            font = font_cache.pil_font(size_px)
            draw.text(pos, text, fill=color, font=font)

    return img


def render_png_bytes(items: List[Dict[str, Any]], size: Tuple[int, int] = DEFAULT_SIZE) -> bytes:
    img = render_whiteboard_image(items, size, font_cache=None)
    buffer = io.BytesIO()
    try:
        img.save(buffer, format="PNG")
        return buffer.getvalue()
    finally:
        buffer.close()
