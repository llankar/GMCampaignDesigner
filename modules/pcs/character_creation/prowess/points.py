"""Prowess point calculation helpers."""

from __future__ import annotations

import re

from .options import DEFAULT_OPTION_NAME, PROWESS_OPTION_BY_LABEL, option_uses_variable_points, parse_variable_points


_OPTION_COST_PATTERN = re.compile(r"^\s*(\d+)\s*pt", flags=re.IGNORECASE)


def _split_option_value(raw_value: str) -> tuple[str, str]:
    """Internal helper for split option value."""
    if ":" not in raw_value:
        return raw_value.strip(), ""
    option_name, option_detail = raw_value.split(":", 1)
    return option_name.strip(), option_detail.strip()


def _option_name_from_label_or_name(option_raw_name: str) -> str:
    """Internal helper for option name from label or name."""
    return PROWESS_OPTION_BY_LABEL.get(option_raw_name, option_raw_name or DEFAULT_OPTION_NAME)


def _option_cost_from_string(option_value: str) -> int:
    """Internal helper for option cost from string."""
    option_raw_name, option_detail = _split_option_value(option_value)
    option_name = _option_name_from_label_or_name(option_raw_name)

    if option_uses_variable_points(option_name):
        return parse_variable_points(option_detail)

    parsed_points_match = _OPTION_COST_PATTERN.match(option_detail)
    if parsed_points_match:
        # Continue with this path when parsed points match is set.
        parsed_points = int(parsed_points_match.group(1))
        if 1 <= parsed_points <= 3:
            return parsed_points
    return 1


def calculate_feat_points_from_options(options: list[str]) -> int:
    """Return spent prowess points for a feat (each option costs at least 1)."""

    return sum(_option_cost_from_string(str(option)) for option in (options or []))
