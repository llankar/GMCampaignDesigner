"""Reusable component style maps built from session dock tokens."""

from __future__ import annotations

from typing import Dict

from .tokens import ANIMATION, COLORS, SPACING, STATES, TYPOGRAPHY


BUTTON_VARIANTS: Dict[str, Dict[str, str | int]] = {
    "idle": {
        "fg_color": COLORS.background_subtle,
        "hover_color": STATES.hover,
        "border_color": COLORS.border_default,
        "text_color": COLORS.text_primary,
    },
    "hover": {
        "fg_color": STATES.hover,
        "hover_color": STATES.active,
        "border_color": COLORS.border_focus,
        "text_color": COLORS.text_primary,
    },
    "active": {
        "fg_color": STATES.active,
        "hover_color": STATES.active,
        "border_color": COLORS.accent_primary,
        "text_color": COLORS.background_canvas,
    },
    "critical": {
        "fg_color": STATES.critical,
        "hover_color": "#F0838B",
        "border_color": "#F4A4AA",
        "text_color": COLORS.background_canvas,
    },
}


ICON_VARIANTS: Dict[str, Dict[str, str]] = {
    "idle": {"fg": STATES.idle, "bg": COLORS.background_surface},
    "hover": {"fg": STATES.hover, "bg": COLORS.background_subtle},
    "active": {"fg": STATES.active, "bg": COLORS.accent_primary_soft},
    "critical": {"fg": STATES.critical, "bg": "#472229"},
}


PANEL_BASE_STYLE: Dict[str, str | int] = {
    "fg_color": COLORS.background_surface,
    "corner_radius": 10,
    "border_width": 1,
    "border_color": COLORS.border_default,
}


TITLE_LABEL_STYLE: Dict[str, str | int] = {
    "text_color": COLORS.text_primary,
    "font": (TYPOGRAPHY.font_family, TYPOGRAPHY.title_size, TYPOGRAPHY.title_weight),
}


BODY_LABEL_STYLE: Dict[str, str | int] = {
    "text_color": COLORS.text_secondary,
    "font": (TYPOGRAPHY.font_family, TYPOGRAPHY.body_size, TYPOGRAPHY.body_weight),
}


ANIMATION_STYLE: Dict[str, int] = {
    "expand_ms": ANIMATION.expand_ms,
    "collapse_ms": ANIMATION.collapse_ms,
    "result_highlight_ms": ANIMATION.result_highlight_ms,
}


def button_style(state: str = "idle") -> Dict[str, str | int]:
    """Return the button style for a given interaction state."""
    return BUTTON_VARIANTS.get(state, BUTTON_VARIANTS["idle"]).copy()


def icon_style(state: str = "idle") -> Dict[str, str]:
    """Return the icon style for a given interaction state."""
    return ICON_VARIANTS.get(state, ICON_VARIANTS["idle"]).copy()


def spacing(value: str = "md") -> int:
    """Expose spacing tokens via string keys for panel layout code."""
    return getattr(SPACING, value, SPACING.md)
