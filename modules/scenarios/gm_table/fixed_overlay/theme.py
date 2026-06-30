"""Theme helpers for the fixed GM Table overlay."""
from __future__ import annotations

from modules.helpers import theme_manager


def get_fixed_overlay_palette(theme: str | None = None) -> dict[str, str]:
    """Return fixed-overlay colors synchronized with the global UI theme."""
    tokens = theme_manager.get_tokens(theme)
    panel_focus = tokens.get("button_fg", "#7DD3FC")
    accent = tokens.get("accent_button_fg") or tokens.get("button_fg", "#F59E0B")
    accent_hover = tokens.get("accent_button_hover") or tokens.get("button_hover", "#D97706")
    panel_bg = tokens.get("panel_bg", "#0F1523")
    panel_alt = tokens.get("panel_alt_bg", "#171F30")
    border = tokens.get("button_border") or tokens.get("button_hover", "#34405A")
    return {
        "table_bg": panel_bg,
        "table_alt": panel_alt,
        "table_line": border,
        "table_chip": tokens.get("button_fg", "#20283A"),
        "panel_bg": panel_bg,
        "panel_alt": panel_alt,
        "panel_border": border,
        "panel_focus": panel_focus,
        "text": "#F4F7FB",
        "muted": "#9EABC2",
        "accent": accent,
        "accent_hover": accent_hover,
        "danger": "#F87171",
        "danger_hover": "#DC2626",
        "button_text_on_accent": "#F4F7FB",
    }
