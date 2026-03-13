from __future__ import annotations

"""Visual theme helpers for the generic editor UI."""

from modules.helpers.theme_manager import get_theme, get_tokens


def _build_editor_palette() -> dict:
    """Build the generic editor palette from the currently selected UI theme."""

    tokens = get_tokens(get_theme())
    accent = tokens.get("button_fg", "#4A8DFF")
    accent_hover = tokens.get("button_hover", "#6BA0FF")
    border = tokens.get("button_border", accent_hover)

    return {
        "surface": "#171A22",
        "surface_alt": "#1F2430",
        "surface_soft": "#252C3A",
        "border": border,
        "text": "#EAF1FF",
        "muted_text": "#A9B5D1",
        "accent": accent,
        "accent_hover": accent_hover,
        "success": "#4ADE80",
        "warning": "#F7C65D",
    }

EDITOR_PALETTE = _build_editor_palette()


def toolbar_entry_style() -> dict:
    return {
        "fg_color": EDITOR_PALETTE["surface_soft"],
        "border_width": 1,
        "border_color": EDITOR_PALETTE["border"],
        "corner_radius": 10,
        "text_color": EDITOR_PALETTE["text"],
    }


def primary_button_style() -> dict:
    return {
        "fg_color": EDITOR_PALETTE["accent"],
        "hover_color": EDITOR_PALETTE["accent_hover"],
        "text_color": "#FFFFFF",
        "corner_radius": 10,
        "border_width": 0,
    }


def option_menu_style() -> dict:
    return {
        "fg_color": EDITOR_PALETTE["accent"],
        "button_color": EDITOR_PALETTE["accent"],
        "button_hover_color": EDITOR_PALETTE["accent_hover"],
        "text_color": "#FFFFFF",
        "corner_radius": 10,
    }


def section_style() -> dict:
    return {
        "fg_color": EDITOR_PALETTE["surface_alt"],
        "border_width": 1,
        "border_color": EDITOR_PALETTE["border"],
        "corner_radius": 12,
    }


def tk_listbox_theme() -> dict:
    """Return a Tk Listbox palette that matches the editor's dark theme."""

    return {
        "bg": EDITOR_PALETTE["surface_soft"],
        "fg": EDITOR_PALETTE["text"],
        "selectbackground": EDITOR_PALETTE["accent"],
        "selectforeground": "#FFFFFF",
        "highlightbackground": EDITOR_PALETTE["border"],
        "highlightcolor": EDITOR_PALETTE["border"],
        "highlightthickness": 1,
        "relief": "flat",
        "bd": 0,
    }
