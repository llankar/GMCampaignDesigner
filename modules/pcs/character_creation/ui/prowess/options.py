"""Backward-compatible re-export for prowess option catalog."""

from ...prowess.options import (
    DEFAULT_OPTION_NAME,
    PROWESS_OPTION_BY_LABEL,
    PROWESS_OPTION_BY_NAME,
    PROWESS_OPTION_LABELS,
    PROWESS_OPTIONS,
    ProwessOption,
    BONUS_DAMAGE_MODES,
    option_uses_variable_points,
    parse_bonus_damage_detail,
    parse_variable_points,
)

__all__ = [
    "ProwessOption",
    "PROWESS_OPTIONS",
    "PROWESS_OPTION_LABELS",
    "PROWESS_OPTION_BY_LABEL",
    "PROWESS_OPTION_BY_NAME",
    "DEFAULT_OPTION_NAME",
    "BONUS_DAMAGE_MODES",
    "option_uses_variable_points",
    "parse_bonus_damage_detail",
    "parse_variable_points",
]
