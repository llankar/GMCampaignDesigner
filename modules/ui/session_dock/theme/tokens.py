"""Design tokens for the session dock UI.

This module centralizes visual primitives so panels can share one cohesive identity.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SpacingScale:
    none: int = 0
    xs: int = 4
    sm: int = 8
    md: int = 12
    lg: int = 16
    xl: int = 24
    xxl: int = 32


@dataclass(frozen=True)
class TypographyHierarchy:
    font_family: str = "Inter"
    title_size: int = 18
    subtitle_size: int = 14
    body_size: int = 13
    caption_size: int = 11
    title_weight: str = "bold"
    subtitle_weight: str = "bold"
    body_weight: str = "normal"
    caption_weight: str = "normal"


@dataclass(frozen=True)
class ColorRoles:
    background_canvas: str = "#0E1118"
    background_surface: str = "#161C27"
    background_subtle: str = "#1E2634"
    border_default: str = "#2C374A"
    border_focus: str = "#4F6FA2"
    text_primary: str = "#E8ECF4"
    text_secondary: str = "#B6C1D4"
    text_muted: str = "#8B98AE"
    accent_primary: str = "#72A4FF"
    accent_primary_soft: str = "#3A527B"


@dataclass(frozen=True)
class StateColors:
    idle: str = "#5C6F91"
    hover: str = "#7F95BD"
    active: str = "#8DB3FF"
    critical: str = "#E66C75"
    success: str = "#63CB9B"
    warning: str = "#E6BC6C"


@dataclass(frozen=True)
class AnimationTimings:
    expand_ms: int = 220
    collapse_ms: int = 180
    result_highlight_ms: int = 700


SPACING = SpacingScale()
TYPOGRAPHY = TypographyHierarchy()
COLORS = ColorRoles()
STATES = StateColors()
ANIMATION = AnimationTimings()
