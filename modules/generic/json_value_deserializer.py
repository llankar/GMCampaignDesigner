"""Safe JSON value deserialization helpers for generic storage rows."""

from __future__ import annotations

import json
from typing import Any

_JSON_PREFIXES = ("{", "[", "\"")


def deserialize_possible_json(value: Any) -> Any:
    """Return decoded JSON for JSON-looking strings, otherwise the original value.

    Generic tables store lists and dictionaries as JSON text, but user-editable
    text fields may also legitimately start with JSON prefix characters.  Those
    malformed JSON-looking values must stay as plain text instead of preventing
    the whole table from loading.
    """
    if not isinstance(value, str):
        return value

    stripped_value = value.strip()
    if not stripped_value.startswith(_JSON_PREFIXES):
        return value

    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return value
