"""Validation helpers for AI-generated scenario entity names."""

from __future__ import annotations

import re
from typing import Any

_MARKDOWN_FENCE_RE = re.compile(r"^```(?:[A-Za-z0-9_-]+)?$", re.IGNORECASE)
_JSON_FRAGMENT_RE = re.compile(r'^"[^"\\]+"\s*:\s*.+,?$')
_SECTION_LABELS = {
    "npc",
    "npcs",
    "location",
    "locations",
    "place",
    "places",
    "secret",
    "secrets",
}


def normalize_generated_entity_name(value: Any) -> str:
    """Return a display-ready generated entity name, or ``""`` if invalid."""
    text = str(value or "").strip()
    if not text:
        return ""

    text = text.strip(" \t\r\n-*•")
    if not text:
        return ""

    if _MARKDOWN_FENCE_RE.fullmatch(text):
        return ""
    if _JSON_FRAGMENT_RE.fullmatch(text):
        return ""
    if text.endswith(":") and text[:-1].strip().casefold() in _SECTION_LABELS:
        return ""
    if not any(char.isalnum() for char in text):
        return ""

    return _strip_balanced_display_quotes(text)


def _strip_balanced_display_quotes(text: str) -> str:
    """Remove one layer of surrounding display quotes from a generated name."""
    quote_pairs = (("\"", "\""), ("'", "'"), ("“", "”"), ("‘", "’"))
    for opening, closing in quote_pairs:
        if text.startswith(opening) and text.endswith(closing) and len(text) >= 2:
            return text[1:-1].strip()
    return text
