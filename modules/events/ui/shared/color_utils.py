"""Utilities for event color utils."""

import re


HEX_COLOR_PATTERN = re.compile(r"^#?[0-9a-fA-F]{6}$")


def normalize_hex_color(value, fallback="#4F8EF7"):
    """Normalize hex color."""
    text = str(value or "").strip()
    if not text:
        return fallback
    if not HEX_COLOR_PATTERN.match(text):
        return fallback
    if not text.startswith("#"):
        text = f"#{text}"
    return text.upper()
