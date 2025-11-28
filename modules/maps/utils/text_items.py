import tkinter as tk
import customtkinter as ctk
from PIL import ImageFont

DEFAULT_TEXT_SIZES = [12, 14, 16, 18, 20, 24, 28, 32, 40, 48, 60]


def prompt_for_text(parent: tk.Widget | None, *, title: str, prompt: str, initial: str = "") -> str | None:
    """Display a simple dialog asking the user for text.

    Returns the entered string or ``None`` if the dialog was cancelled or left blank.
    """
    try:
        dialog = ctk.CTkInputDialog(text=prompt, title=title)
        if initial:
            try:
                dialog._entry.insert(0, initial)  # type: ignore[attr-defined]
            except Exception:
                pass
        result = dialog.get_input()
    except Exception:
        from tkinter import simpledialog

        result = simpledialog.askstring(title, prompt, initialvalue=initial, parent=parent)
    if result is None:
        return None
    result = str(result).strip()
    return result if result else None


def create_text_item(text: str, position: tuple[float, float], *, color: str, size: int) -> dict:
    return {
        "type": "text",
        "text": text,
        "position": position,
        "color": color,
        "text_size": int(size),
        "canvas_ids": (),
    }


class TextFontCache:
    """Cache for tkinter and PIL fonts keyed by size."""

    def __init__(self):
        self._tk_fonts: dict[int, ctk.CTkFont] = {}
        self._pil_fonts: dict[int, ImageFont.FreeTypeFont | ImageFont.ImageFont] = {}

    def tk_font(self, size: int) -> ctk.CTkFont:
        normalized = max(8, int(size))
        if normalized not in self._tk_fonts:
            self._tk_fonts[normalized] = ctk.CTkFont(size=normalized)
        return self._tk_fonts[normalized]

    def pil_font(self, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
        normalized = max(8, int(size))
        if normalized not in self._pil_fonts:
            try:
                self._pil_fonts[normalized] = ImageFont.truetype("DejaVuSans.ttf", normalized)
            except Exception:
                self._pil_fonts[normalized] = ImageFont.load_default()
        return self._pil_fonts[normalized]


def approximate_text_bbox(position: tuple[float, float], *, text: str, size: int, zoom: float, pan: tuple[float, float], padding: float = 6.0) -> tuple[float, float, float, float]:
    """Return an approximate screen-space bounding box for a text item."""
    xw, yw = position
    screen_x = pan[0] + xw * zoom
    screen_y = pan[1] + yw * zoom
    avg_char_width = max(size * 0.55, 6)
    width = avg_char_width * max(len(text), 1)
    height = max(size * 1.2, 10)
    pad = padding + (size * 0.15)
    return (
        screen_x - pad,
        screen_y - pad,
        screen_x + width + pad,
        screen_y + height + pad,
    )


def text_hit_test(canvas: tk.Canvas | None, item: dict, *, screen_point: tuple[float, float], radius: float, zoom: float, pan: tuple[float, float]) -> bool:
    """Return True if the eraser at *screen_point* should remove the given text item."""
    if item.get("type") != "text":
        return False
    text_id = None
    canvas_ids = item.get("canvas_ids") or ()
    if canvas_ids:
        text_id = canvas_ids[0]
    bbox = None
    if canvas and text_id:
        try:
            bbox = canvas.bbox(text_id)
        except tk.TclError:
            bbox = None
    if not bbox:
        bbox = approximate_text_bbox(
            item.get("position", (0, 0)),
            text=item.get("text", ""),
            size=int(item.get("text_size", 12)),
            zoom=zoom,
            pan=pan,
        )
    if not bbox:
        return False
    sx, sy = screen_point
    expanded = (
        bbox[0] - radius,
        bbox[1] - radius,
        bbox[2] + radius,
        bbox[3] + radius,
    )
    return expanded[0] <= sx <= expanded[2] and expanded[1] <= sy <= expanded[3]
