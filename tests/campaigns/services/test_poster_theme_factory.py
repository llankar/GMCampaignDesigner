"""Tests for poster theme token composition and contrast safeguards."""
from __future__ import annotations

import re
from dataclasses import asdict

from modules.campaigns.services.poster_export import build_poster_theme_from_tokens, contrast_ratio


HEX_PATTERN = re.compile(r"^#[0-9a-f]{6}$")


def test_build_theme_from_tokens_generates_valid_hex_values() -> None:
    tokens = {
        "panel_bg": "#111c2a",
        "panel_alt_bg": "#132133",
        "accent_button_fg": "#303c5a",
        "button_fg": "#0077CC",
        "button_border": "#005fa3",
    }

    theme = build_poster_theme_from_tokens(tokens)

    for value in asdict(theme).values():
        assert HEX_PATTERN.match(value)


def test_build_theme_falls_back_to_safe_text_and_border_when_contrast_is_low() -> None:
    low_contrast_tokens = {
        "panel_bg": "#202020",
        "panel_alt_bg": "#212121",
        "accent_button_fg": "#232323",
        "button_fg": "#222222",
        "button_border": "#232323",
    }

    theme = build_poster_theme_from_tokens(low_contrast_tokens, min_text_contrast=4.5)

    assert contrast_ratio(theme.text_primary, theme.surface) >= 4.5
    assert contrast_ratio(theme.border, theme.surface) >= 1.5
    assert contrast_ratio(theme.accent, theme.surface) >= 3.0
