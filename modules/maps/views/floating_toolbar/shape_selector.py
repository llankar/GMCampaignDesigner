"""Icon-style shape selector for the floating map toolbar."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable

import customtkinter as ctk

from modules.ui.tooltip import ToolTip
from modules.maps.views.floating_toolbar.layout import TEXT_MUTED, create_row, add_small_label


class ShapeIconSelector(ctk.CTkFrame):
    """Two-button rectangle/oval selector that replaces a text dropdown."""

    _DEFAULT_STYLE = {
        "fg_color": "#2f2f2f",
        "hover_color": "#3a3a3a",
        "border_color": "#4a4a4a",
        "border_width": 1,
        "text_color": TEXT_MUTED,
    }
    _ACTIVE_STYLE = {
        "fg_color": "#28a874",
        "hover_color": "#239164",
        "border_color": "#35c98c",
        "border_width": 1,
        "text_color": "#ffffff",
    }

    def __init__(self, parent: tk.Misc, command: Callable[[str], None]) -> None:
        """Build a compact pair of shape buttons."""
        super().__init__(parent, fg_color="transparent")
        self._command = command
        self._selected_value = "Rectangle"
        self._buttons: dict[str, ctk.CTkButton] = {}
        self._build_buttons()
        self.set("Rectangle", invoke=False)

    def _build_buttons(self) -> None:
        items = (("Rectangle", "▭", "Rectangle brush"), ("Oval", "⬭", "Oval brush"))
        for value, icon, tooltip in items:
            button = ctk.CTkButton(
                self,
                text=icon,
                width=28,
                height=26,
                corner_radius=8,
                font=ctk.CTkFont(size=15, weight="bold"),
                command=lambda selected=value: self.set(selected),
                **self._DEFAULT_STYLE,
            )
            button.pack(side="top", anchor="w", padx=0, pady=(0, 3))
            self._buttons[value] = button
            ToolTip(button, tooltip)

    def set(self, value: str, *, invoke: bool = True) -> None:
        """Select a shape and optionally notify the controller."""
        if value not in self._buttons:
            value = "Rectangle"
        self._selected_value = value
        for button_value, button in self._buttons.items():
            try:
                button.configure(**(self._ACTIVE_STYLE if button_value == value else self._DEFAULT_STYLE))
            except tk.TclError:
                continue
        if invoke:
            self._command(value)

    def get(self) -> str:
        """Return the selected controller value."""
        return self._selected_value


def add_shape_icon_selector(parent: tk.Misc, command: Callable[[str], None]) -> ShapeIconSelector:
    """Add a labeled rectangle/oval icon selector row."""
    row = create_row(parent)
    add_small_label(row, "Shape")
    selector = ShapeIconSelector(row, command)
    selector.pack(side="top", anchor="w", padx=0, pady=(0, 1))
    return selector
