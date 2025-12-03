import tkinter as tk
import customtkinter as ctk
from PIL import ImageFont

DEFAULT_TEXT_SIZES = [12, 14, 16, 18, 20, 24, 28, 32, 40, 48, 60]


class _MultilineTextDialog(ctk.CTkToplevel):
    """A small reusable multi-line text input dialog."""

    def __init__(self, parent: tk.Widget | None, *, title: str, prompt: str, initial: str = ""):
        super().__init__(parent)
        self.title(title)
        self.result: str | None = None
        self.geometry("520x320")
        self.minsize(420, 260)
        self.transient(parent)
        self.grab_set()

        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        prompt_label = ctk.CTkLabel(self, text=prompt, anchor="w", justify="left")
        prompt_label.grid(row=0, column=0, padx=14, pady=(14, 8), sticky="ew")

        self.textbox = ctk.CTkTextbox(self, wrap="word", width=480, height=180)
        self.textbox.grid(row=1, column=0, padx=14, pady=(0, 10), sticky="nsew")
        if initial:
            try:
                self.textbox.insert("1.0", initial)
                self.textbox.edit_modified(False)
            except tk.TclError:
                pass
        self.textbox.focus_set()

        button_row = ctk.CTkFrame(self)
        button_row.grid(row=2, column=0, padx=14, pady=(4, 14), sticky="e")

        cancel_btn = ctk.CTkButton(button_row, text="Cancel", command=self._on_cancel, width=90)
        cancel_btn.pack(side="right", padx=(6, 0))
        ok_btn = ctk.CTkButton(button_row, text="Save", command=self._on_ok, width=90)
        ok_btn.pack(side="right")

        self.bind("<Escape>", lambda _e: self._on_cancel())
        self.bind("<Control-Return>", lambda _e: self._on_ok())

    def _on_ok(self):
        try:
            value = self.textbox.get("1.0", "end")
        except tk.TclError:
            value = ""
        cleaned = value.strip()
        self.result = cleaned if cleaned else None
        self.destroy()

    def _on_cancel(self):
        self.result = None
        self.destroy()

    def get_input(self) -> str | None:
        self.wait_window(self)
        return self.result


def prompt_for_text(parent: tk.Widget | None, *, title: str, prompt: str, initial: str = "") -> str | None:
    """Display a dialog asking the user for text (multi-line aware)."""
    try:
        dialog = _MultilineTextDialog(parent, title=title, prompt=prompt, initial=initial)
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
    """Cache for tkinter and PIL fonts keyed by size using a shared family."""

    def __init__(self, family: str = "Arial"):
        self._family = family or "Arial"
        self._resolved_family = None
        self._tk_fonts: dict[int, ctk.CTkFont] = {}
        self._pil_fonts: dict[int, ImageFont.FreeTypeFont | ImageFont.ImageFont] = {}

    def tk_font(self, size: int) -> ctk.CTkFont:
        normalized = max(8, int(size))
        if normalized not in self._tk_fonts:
            font = ctk.CTkFont(family=self._family, size=normalized)
            try:
                self._resolved_family = font.actual().get("family") or self._family
            except Exception:
                self._resolved_family = self._family
            self._tk_fonts[normalized] = font
        return self._tk_fonts[normalized]

    def pil_font(self, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
        normalized = max(8, int(size))
        if normalized not in self._pil_fonts:
            try:
                family = self._resolved_family or self._family
                self._pil_fonts[normalized] = ImageFont.truetype(family, normalized)
            except Exception:
                try:
                    # Pillow bundles DejaVuSans, which provides a predictable size
                    # even when the requested Tk font family is unavailable on the host.
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
