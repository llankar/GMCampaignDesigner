"""Slim option-menu helpers for narrow floating map palettes."""

from __future__ import annotations

import tkinter as tk
from typing import Any

import customtkinter as ctk

from modules.maps.views.floating_toolbar.layout import CONTROL_FONT_SIZE
from modules.maps.views.floating_toolbar.compact_widths import width_for_display_text


def create_slim_option_menu(parent: tk.Misc, **kwargs: Any) -> ctk.CTkOptionMenu:
    """Create a compact option menu with its arrow area visually removed."""
    font = kwargs.pop("font", ctk.CTkFont(size=CONTROL_FONT_SIZE))
    dropdown_font = kwargs.pop("dropdown_font", ctk.CTkFont(size=CONTROL_FONT_SIZE))
    command = kwargs.get("command")
    explicit_width = "width" in kwargs
    initial_value = kwargs.pop("initial_value", None)
    if not explicit_width:
        values = kwargs.get("values") or []
        initial_value = initial_value or (values[0] if values else "")
        kwargs["width"] = width_for_display_text(initial_value)

    def _compact_command(value: str) -> None:
        set_menu_width_to_text(menu, value)
        if callable(command):
            command(value)

    if command is not None:
        kwargs["command"] = _compact_command

    menu = ctk.CTkOptionMenu(parent, font=font, dropdown_font=dropdown_font, **kwargs)
    if not explicit_width:
        _wrap_set_for_compact_width(menu)
    hide_option_menu_arrow(menu)
    if not explicit_width:
        set_menu_width_to_text(menu, initial_value)
    return menu


def hide_option_menu_arrow(menu: ctk.CTkOptionMenu) -> None:
    """
    Make a CTkOptionMenu use the whole control width for text.

    CustomTkinter draws the dropdown arrow and right-side button on the menu's
    internal canvas. Keeping the menu itself clickable but removing that visual
    split makes narrow toolbar controls read more like compact pills.
    """
    try:
        fg_color = menu.cget("fg_color")
        hover_color = menu.cget("fg_color")
        menu.configure(
            anchor="w",
            button_color=fg_color,
            button_hover_color=hover_color,
            dropdown_font=ctk.CTkFont(size=CONTROL_FONT_SIZE),
            font=ctk.CTkFont(size=CONTROL_FONT_SIZE),
        )
    except (tk.TclError, ValueError):
        return

    _expand_text_label(menu)
    _erase_arrow(menu)
    menu.after_idle(lambda: (_expand_text_label(menu), _erase_arrow(menu)))


def _expand_text_label(menu: ctk.CTkOptionMenu) -> None:
    """Let the internal text label span the area normally reserved for the arrow."""
    label = getattr(menu, "_text_label", None)
    if label is None:
        return
    try:
        label.grid_configure(column=0, columnspan=2, sticky="ew", padx=(6, 6))
        label.configure(anchor="w")
    except tk.TclError:
        return


def _erase_arrow(menu: ctk.CTkOptionMenu) -> None:
    """Remove the canvas arrow tag when supported by the CustomTkinter version."""
    canvas = getattr(menu, "_canvas", None)
    if canvas is None:
        return
    try:
        canvas.delete("dropdown_arrow")
    except tk.TclError:
        return


def set_menu_width_to_text(menu: ctk.CTkOptionMenu, value: object | None = None) -> None:
    """Resize an option menu to the text it currently displays."""
    if value is None:
        try:
            value = menu.get()
        except tk.TclError:
            value = ""
    try:
        menu.configure(width=width_for_display_text(value))
    except tk.TclError:
        return


def _wrap_set_for_compact_width(menu: ctk.CTkOptionMenu) -> None:
    """Keep programmatic selections as compact as user-driven selections."""
    original_set = menu.set

    def _set_and_resize(value: str) -> None:
        original_set(value)
        set_menu_width_to_text(menu, value)

    menu.set = _set_and_resize
