"""Shared style tokens and semantic variants for compact overlay bars."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Mapping

VariantName = Literal["default", "accent", "success", "muted", "warning"]


@dataclass(frozen=True)
class VariantStyle:
    """Semantic color set for chips/buttons."""

    fg: str
    hover: str
    border: str
    text: str
    text_disabled: str


@dataclass(frozen=True)
class BarStyleTokens:
    """Shared token palette for compact bar windows."""

    spacing_2xs: int = 2
    spacing_xs: int = 4
    spacing_sm: int = 6
    spacing_md: int = 8
    spacing_lg: int = 12

    collapse_button_width: int = 16
    bar_outer_pad_x: int = 8
    bar_outer_pad_y_audio: int = 8
    bar_outer_pad_y_dice: int = 4

    corner_radius_none: int = 0
    corner_radius_chip: int = 10

    border_width_thin: int = 1

    font_size_header: int = 13
    font_size_body: int = 14
    font_size_result: int = 16
    font_size_total: int = 18

    emphasis_text_muted: str = "#9fb2ce"
    emphasis_text_bright: str = "#ffffff"
    emphasis_text_soft: str = "#d3dced"

    state_success_fg: str = "#2fa572"
    state_success_hover: str = "#23865a"
    state_warning_fg: str = "#c4802c"
    state_warning_hover: str = "#9c6421"
    success_button_fg: str = "#2fa572"
    success_button_hover: str = "#23865a"


def shared_bar_tokens() -> BarStyleTokens:
    """Return immutable shared spacing/shape/typography tokens."""

    return BarStyleTokens()


def build_bar_variants(theme_tokens: Mapping[str, str] | None) -> dict[VariantName, VariantStyle]:
    """Build semantic variant colors using theme tokens with robust fallbacks."""

    palette = theme_tokens or {}

    default_fg = str(palette.get("button_fg", "#2d3a57"))
    default_hover = str(palette.get("button_hover", "#3a4d73"))
    default_border = str(palette.get("button_border", "#1f2a3d"))
    accent_fg = str(palette.get("accent_button_fg", default_fg))
    accent_hover = str(palette.get("accent_button_hover", default_hover))

    base = shared_bar_tokens()

    return {
        "default": VariantStyle(
            fg=default_fg,
            hover=default_hover,
            border=default_border,
            text=base.emphasis_text_bright,
            text_disabled=base.emphasis_text_bright,
        ),
        "accent": VariantStyle(
            fg=accent_fg,
            hover=accent_hover,
            border=accent_hover,
            text=base.emphasis_text_bright,
            text_disabled=base.emphasis_text_bright,
        ),
        "success": VariantStyle(
            fg=base.success_button_fg,
            hover=base.success_button_hover,
            border=base.success_button_hover,
            text=base.emphasis_text_bright,
            text_disabled=base.emphasis_text_bright,
        ),
        "muted": VariantStyle(
            fg=str(palette.get("panel_alt_bg", "#132133")),
            hover=str(palette.get("panel_alt_bg", "#132133")),
            border=default_border,
            text=base.emphasis_text_soft,
            text_disabled=base.emphasis_text_soft,
        ),
        "warning": VariantStyle(
            fg=base.state_warning_fg,
            hover=base.state_warning_hover,
            border=base.state_warning_hover,
            text=base.emphasis_text_bright,
            text_disabled=base.emphasis_text_bright,
        ),
    }


def variant_style(
    theme_tokens: Mapping[str, str] | None,
    variant: VariantName,
) -> VariantStyle:
    """Resolve one semantic variant style."""

    return build_bar_variants(theme_tokens)[variant]
