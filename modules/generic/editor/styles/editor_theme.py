from __future__ import annotations

"""Visual theme helpers for the generic editor UI."""

EDITOR_PALETTE = {
    "surface": "#171A22",
    "surface_alt": "#1F2430",
    "surface_soft": "#252C3A",
    "border": "#313A4E",
    "text": "#EAF1FF",
    "muted_text": "#A9B5D1",
    "accent": "#4A8DFF",
    "accent_hover": "#6BA0FF",
    "success": "#4ADE80",
    "warning": "#F7C65D",
}


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
