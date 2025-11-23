import tkinter as tk
import tkinter.font as tkfont
from typing import Any, Dict, Iterable, Tuple

from modules.helpers.logging_helper import log_module_import
from modules.helpers.text_helpers import deserialize_possible_json, normalize_rtf_json

log_module_import(__name__)


def _target_text_widget(widget: tk.Text) -> tk.Text:
    """Return a ``tk.Text``-compatible object for CTkTextbox/Text widgets."""

    return getattr(widget, "_textbox", widget)


def _coerce_rtf_payload(value: Any) -> Dict[str, Any]:
    """Return a normalized RTF-like payload with ``text`` and ``formatting`` keys."""

    parsed = deserialize_possible_json(value)
    if isinstance(parsed, dict):
        return normalize_rtf_json(parsed)
    return {"text": str(parsed or ""), "formatting": {}}


def _index_from_offset(offset: Any) -> str:
    """Convert numeric offsets to ``tk.Text`` indices ("1.0 + Nc")."""

    if isinstance(offset, str) and "." in offset:
        return offset
    try:
        return f"1.0 + {int(offset)} chars"
    except (TypeError, ValueError):
        return "1.0"


def _configure_base_tags(text_widget: tk.Text, base_font: Tuple[str, int]):
    """Ensure common formatting tags exist on the widget."""

    family, size = base_font
    text_widget.tag_configure("bold", font=(family, size, "bold"))
    text_widget.tag_configure("italic", font=(family, size, "italic"))
    text_widget.tag_configure("underline", font=(family, size, "underline"))
    text_widget.tag_configure("left", justify="left")
    text_widget.tag_configure("center", justify="center")
    text_widget.tag_configure("right", justify="right")


def _ensure_dynamic_tag(text_widget: tk.Text, tag: str, base_font: tkfont.Font):
    """Create size_/color_ tags on demand so they render correctly."""

    if text_widget.tag_cget(tag, "font") or text_widget.tag_cget(tag, "foreground"):
        return

    if tag.startswith("size_"):
        try:
            size = int(tag.split("_", 1)[1])
        except (TypeError, ValueError):
            return
        text_widget.tag_configure(tag, font=(base_font.actual("family"), size))
    elif tag.startswith("color_"):
        text_widget.tag_configure(tag, foreground=tag.split("_", 1)[1])


def render_rtf_to_text_widget(widget: tk.Text, value: Any, base_font: Tuple[str, int] = ("Arial", 12)) -> None:
    """Render RTF-style content (text + formatting ranges) into a text widget."""

    text_widget = _target_text_widget(widget)
    text_widget.configure(state="normal")
    text_widget.delete("1.0", tk.END)

    payload = _coerce_rtf_payload(value)
    text = payload.get("text", "")
    formatting: Dict[str, Iterable[Tuple[Any, Any]]] = payload.get("formatting", {}) or {}

    text_widget.insert("1.0", text)

    tk_font = tkfont.Font(font=text_widget.cget("font"))
    _configure_base_tags(text_widget, (tk_font.actual("family"), tk_font.actual("size")))

    for tag, ranges in formatting.items():
        if tag.startswith(("size_", "color_")):
            _ensure_dynamic_tag(text_widget, tag, tk_font)
        for start, end in ranges:
            idx1 = _index_from_offset(start)
            idx2 = _index_from_offset(end)
            try:
                text_widget.tag_add(tag, idx1, idx2)
            except tk.TclError:
                # Skip invalid ranges but continue rendering other tags.
                continue

    text_widget.configure(state="disabled")
