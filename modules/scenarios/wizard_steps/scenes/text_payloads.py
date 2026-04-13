"""Text payload normalization helpers for scenario scene editors."""

from __future__ import annotations

import ast
import json
from typing import Any

from modules.helpers.text_helpers import coerce_text


def extract_plain_scene_text(value: Any) -> str:
    """Return user-facing plain text for scene Summary/Text payloads.

    Some historical payloads stored longtext values as a serialized dictionary
    string, e.g. ``"{'text': '...', 'formatting': {...}}"``.  This helper
    detects those values and extracts the textual content so UI editors don't
    display raw Python/JSON structures.
    """

    if isinstance(value, str):
        raw = value.strip()
        if raw.startswith("{") or raw.startswith("["):
            for parser in (json.loads, ast.literal_eval):
                try:
                    parsed = parser(raw)
                except (ValueError, SyntaxError, TypeError):
                    continue
                if isinstance(parsed, (dict, list)):
                    return coerce_text(parsed).strip()
    return coerce_text(value).strip()
