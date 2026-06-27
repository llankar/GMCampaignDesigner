"""Inline annotation controls for GM Table desks."""

from __future__ import annotations

from collections.abc import Callable
import tkinter as tk

import customtkinter as ctk


COLOR_SWATCHES: tuple[tuple[str, str], ...] = (
    ("Ink", "#1F2937"),
    ("Sepia", "#241A10"),
    ("Ruby", "#DC2626"),
    ("Amber", "#D97706"),
    ("Emerald", "#059669"),
    ("Sky", "#0284C7"),
    ("Violet", "#7C3AED"),
    ("Chalk", "#F8FAFC"),
)
TEXT_SIZE_OPTIONS = (12, 14, 16, 18, 20, 24, 28, 32, 36, 42, 48, 56, 64)
STROKE_WIDTH_OPTIONS = (2, 3, 4, 5, 6, 8, 10, 12)
DEFAULT_STYLES: dict[str, dict[str, object]] = {
    "draw": {"fill": "#1F2937", "width": 3},
    "text": {"fill": "#241A10", "font_size": 18},
}


class DeskAnnotationToolbar(ctk.CTkFrame):
    """Compact inline desk annotation toolbar with swatches and size controls."""

    def __init__(
        self,
        master,
        *,
        palette: dict[str, str],
        on_tool_selected: Callable[[str], None],
        on_style_changed: Callable[[str, dict[str, object]], None],
        on_clear: Callable[[], None],
    ) -> None:
        super().__init__(
            master,
            fg_color=palette["table_chip"],
            corner_radius=16,
            border_width=1,
            border_color=palette["table_line"],
        )
        self._palette = palette
        self._on_tool_selected = on_tool_selected
        self._on_style_changed = on_style_changed
        self._on_clear = on_clear
        self._active_tool = "draw"
        self._styles = {tool: dict(style) for tool, style in DEFAULT_STYLES.items()}
        self._swatch_buttons: dict[str, ctk.CTkButton] = {}
        self._tool_buttons: dict[str, ctk.CTkButton] = {}
        self._text_size_var = tk.StringVar(value=str(DEFAULT_STYLES["text"]["font_size"]))
        self._stroke_width_var = tk.StringVar(value=str(DEFAULT_STYLES["draw"]["width"]))

        self._build()
        self._refresh_controls()

    def style_for_tool(self, tool: str) -> dict[str, object]:
        """Return a copy of the current style for a desk annotation tool."""
        normalized = "text" if str(tool).lower() == "text" else "draw"
        return dict(self._styles[normalized])

    def set_active_tool(self, tool: str) -> None:
        """Refresh the toolbar selection without invoking callbacks."""
        normalized = "text" if str(tool).lower() == "text" else "draw"
        self._active_tool = normalized
        self._refresh_controls()

    def _build(self) -> None:
        label = ctk.CTkLabel(
            self,
            text="Marks",
            text_color=self._palette["muted"],
            font=ctk.CTkFont(size=11, weight="bold"),
        )
        label.pack(side="left", padx=(10, 6))

        self._tool_buttons["draw"] = ctk.CTkButton(
            self,
            text="Draw",
            width=54,
            height=26,
            corner_radius=13,
            command=lambda: self._select_tool("draw"),
        )
        self._tool_buttons["draw"].pack(side="left", padx=(0, 4))

        self._tool_buttons["text"] = ctk.CTkButton(
            self,
            text="Text",
            width=52,
            height=26,
            corner_radius=13,
            command=lambda: self._select_tool("text"),
        )
        self._tool_buttons["text"].pack(side="left", padx=(0, 8))

        for name, color in COLOR_SWATCHES:
            button = ctk.CTkButton(
                self,
                text="",
                width=22,
                height=22,
                corner_radius=11,
                fg_color=color,
                hover_color=color,
                border_width=1,
                border_color=self._palette["table_line"],
                command=lambda value=color: self._select_color(value),
            )
            button.pack(side="left", padx=(0, 4))
            self._swatch_buttons[color.upper()] = button

        self._stroke_menu = ctk.CTkOptionMenu(
            self,
            values=[str(width) for width in STROKE_WIDTH_OPTIONS],
            variable=self._stroke_width_var,
            width=58,
            height=26,
            fg_color=self._palette["table_alt"],
            button_color=self._palette["accent"],
            button_hover_color="#D97706",
            dropdown_fg_color=self._palette["table_alt"],
            dropdown_hover_color="#283146",
            text_color=self._palette["text"],
            dropdown_text_color=self._palette["text"],
            command=lambda _value: self._update_size(),
        )
        self._stroke_menu.pack(side="left", padx=(4, 0))

        self._text_menu = ctk.CTkOptionMenu(
            self,
            values=[str(size) for size in TEXT_SIZE_OPTIONS],
            variable=self._text_size_var,
            width=64,
            height=26,
            fg_color=self._palette["table_alt"],
            button_color=self._palette["accent"],
            button_hover_color="#D97706",
            dropdown_fg_color=self._palette["table_alt"],
            dropdown_hover_color="#283146",
            text_color=self._palette["text"],
            dropdown_text_color=self._palette["text"],
            command=lambda _value: self._update_size(),
        )
        self._text_menu.pack(side="left", padx=(4, 0))

        ctk.CTkButton(
            self,
            text="Clear",
            width=56,
            height=26,
            fg_color="#2B1C23",
            hover_color="#40222B",
            text_color=self._palette["text"],
            corner_radius=13,
            command=self._on_clear,
        ).pack(side="left", padx=(6, 8))

    def _select_tool(self, tool: str) -> None:
        self.set_active_tool(tool)
        self._on_tool_selected(self._active_tool)

    def _select_color(self, color: str) -> None:
        self._styles[self._active_tool]["fill"] = color.upper()
        self._emit_style_change()
        self._refresh_controls()

    def _update_size(self) -> None:
        if self._active_tool == "text":
            self._styles["text"]["font_size"] = _coerce_option(
                self._text_size_var.get(), TEXT_SIZE_OPTIONS, int(DEFAULT_STYLES["text"]["font_size"])
            )
        else:
            self._styles["draw"]["width"] = _coerce_option(
                self._stroke_width_var.get(), STROKE_WIDTH_OPTIONS, int(DEFAULT_STYLES["draw"]["width"])
            )
        self._emit_style_change()

    def _emit_style_change(self) -> None:
        self._on_style_changed(self._active_tool, self.style_for_tool(self._active_tool))

    def _refresh_controls(self) -> None:
        active_color = str(self._styles[self._active_tool].get("fill") or "").upper()
        for color, button in self._swatch_buttons.items():
            button.configure(
                border_width=3 if color == active_color else 1,
                border_color=self._palette["panel_focus"] if color == active_color else self._palette["table_line"],
            )
        for tool, button in self._tool_buttons.items():
            is_active = tool == self._active_tool
            button.configure(
                fg_color=self._palette["accent"] if is_active else self._palette["table_alt"],
                hover_color="#D97706" if is_active else "#283146",
                text_color="#10131B" if is_active else self._palette["text"],
            )
        if self._active_tool == "text":
            self._text_menu.configure(state="normal")
            self._stroke_menu.configure(state="disabled")
        else:
            self._text_menu.configure(state="disabled")
            self._stroke_menu.configure(state="normal")


def _coerce_option(value, options: tuple[int, ...], fallback: int) -> int:
    """Coerce a menu value to a supported option."""
    try:
        numeric = int(value)
    except Exception:
        return fallback
    return numeric if numeric in options else fallback
