from __future__ import annotations

"""Visual theme helpers for the generic editor UI."""

from modules.helpers import theme_manager

_BASE_PALETTE = {
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

_THEME_OVERRIDES = {
    theme_manager.THEME_DEFAULT: {
        "surface": "#171A22",
        "surface_alt": "#1F2430",
        "surface_soft": "#252C3A",
        "border": "#313A4E",
        "text": "#EAF1FF",
        "muted_text": "#A9B5D1",
    },
    theme_manager.THEME_MEDIEVAL: {
        "surface": "#1F1913",
        "surface_alt": "#2A2119",
        "surface_soft": "#33281D",
        "border": "#5C4330",
        "text": "#F7E9D2",
        "muted_text": "#C9AE8A",
    },
    theme_manager.THEME_SF: {
        "surface": "#101912",
        "surface_alt": "#14211A",
        "surface_soft": "#193025",
        "border": "#255641",
        "text": "#E5FFF2",
        "muted_text": "#9ACDB2",
    },
}


def get_editor_palette(theme: str | None = None) -> dict:
    """Return the editor palette synchronized with the global UI theme."""

    key = (theme or theme_manager.get_theme()).strip().lower()
    palette = dict(_BASE_PALETTE)
    palette.update(_THEME_OVERRIDES.get(key, _THEME_OVERRIDES[theme_manager.THEME_DEFAULT]))

    tokens = theme_manager.get_tokens(key)
    palette["accent"] = tokens.get("button_fg", palette["accent"])
    palette["accent_hover"] = tokens.get("button_hover", palette["accent_hover"])

    return palette


class _EditorPaletteProxy(dict):
    """Backwards-compatible mapping that resolves values from the active theme."""

    def __getitem__(self, key):
        return get_editor_palette()[key]

    def get(self, key, default=None):
        return get_editor_palette().get(key, default)


EDITOR_PALETTE = _EditorPaletteProxy()


def toolbar_entry_style() -> dict:
    palette = get_editor_palette()
    return {
        "fg_color": palette["surface_soft"],
        "border_width": 1,
        "border_color": palette["border"],
        "corner_radius": 10,
        "text_color": palette["text"],
    }


def primary_button_style() -> dict:
    palette = get_editor_palette()
    return {
        "fg_color": palette["accent"],
        "hover_color": palette["accent_hover"],
        "text_color": "#FFFFFF",
        "corner_radius": 10,
        "border_width": 0,
    }


def option_menu_style() -> dict:
    palette = get_editor_palette()
    return {
        "fg_color": palette["accent"],
        "button_color": palette["accent"],
        "button_hover_color": palette["accent_hover"],
        "text_color": "#FFFFFF",
        "corner_radius": 10,
    }


def section_style() -> dict:
    palette = get_editor_palette()
    return {
        "fg_color": palette["surface_alt"],
        "border_width": 1,
        "border_color": palette["border"],
        "corner_radius": 12,
    }


def tk_listbox_theme() -> dict:
    """Return a Tk Listbox palette that matches the editor's dark theme."""

    palette = get_editor_palette()

    return {
        "bg": palette["surface_soft"],
        "fg": palette["text"],
        "selectbackground": palette["accent"],
        "selectforeground": "#FFFFFF",
        "highlightbackground": palette["border"],
        "highlightcolor": palette["border"],
        "highlightthickness": 1,
        "relief": "flat",
        "bd": 0,
    }
