"""Helpers for rendering the GM Table minimized-panel tray."""

from __future__ import annotations

from modules.scenarios.gm_table.panel_skins import PanelSkin

MINIMIZED_TRAY_BUTTON_WIDTH = 118
MINIMIZED_TRAY_BUTTON_GAP = 8
MINIMIZED_TRAY_BUTTON_MIN_COLUMNS = 1
MINIMIZED_TRAY_NARROW_BREAKPOINT = 360
MINIMIZED_TRAY_TITLE_LIMIT = 18
DEFAULT_TRAY_TEXT_COLOR = "#F4F7FB"


def readable_text_color(color: str, *, fallback: str = DEFAULT_TRAY_TEXT_COLOR) -> str:
    """Return a readable text color for a solid ``#RRGGBB`` background."""
    value = str(color or "").strip().lstrip("#")
    if len(value) != 6:
        return fallback
    try:
        red = int(value[0:2], 16)
        green = int(value[2:4], 16)
        blue = int(value[4:6], 16)
    except ValueError:
        return fallback
    brightness = red * 0.299 + green * 0.587 + blue * 0.114
    return "#111827" if brightness > 158 else "#F8FAFC"


def compact_tray_title(title: str) -> str:
    """Return a button title that remains legible in compact tray layouts."""
    clean_title = " ".join(str(title or "Panel").split()) or "Panel"
    if len(clean_title) <= MINIMIZED_TRAY_TITLE_LIMIT:
        return clean_title
    return f"{clean_title[: MINIMIZED_TRAY_TITLE_LIMIT - 1].rstrip()}…"


def minimized_tray_button_style(skin: PanelSkin) -> dict[str, object]:
    """Return a compact restore-button style matching a panel's physical skin."""
    if skin.show_spine:
        fg_color = skin.border_color
        hover_color = skin.header_color
        border_color = skin.accent_color
        corner_radius = 8
    elif skin.show_file_tab:
        fg_color = skin.header_color
        hover_color = skin.accent_color
        border_color = skin.border_color
        corner_radius = 14
    elif skin.show_page_edges:
        fg_color = skin.body_color
        hover_color = skin.header_color
        border_color = skin.border_color
        corner_radius = 10
    else:
        fg_color = skin.control_bg
        hover_color = skin.control_hover
        border_color = skin.panel_border
        corner_radius = 12
    return {
        "fg_color": fg_color,
        "hover_color": hover_color,
        "border_color": border_color,
        "text_color": readable_text_color(str(fg_color)),
        "corner_radius": corner_radius,
    }


def minimized_tray_columns(available_width: int) -> int:
    """Return the number of fixed-width tray buttons that fit in a row."""
    safe_width = max(MINIMIZED_TRAY_BUTTON_WIDTH, int(available_width or 0))
    button_span = MINIMIZED_TRAY_BUTTON_WIDTH + MINIMIZED_TRAY_BUTTON_GAP
    return max(MINIMIZED_TRAY_BUTTON_MIN_COLUMNS, safe_width // button_span)
