"""Safe JSON value parsing for generic storage rows."""

from __future__ import annotations

import json
from typing import Any

_JSON_PREFIXES = ("{", "[", "\"")
_JSON_PARSE_EXCEPTIONS = (json.JSONDecodeError, TypeError, ValueError, StopIteration)


def deserialize_possible_json(value: Any) -> Any:
    """Decode JSON-looking strings while preserving plain text on failures.

    Generic tables persist structured values (lists/dicts/RTF payloads) as JSON
    text.  Some user-authored notes can still start with JSON prefix characters
    such as ``[`` or ``{`` without being valid JSON.  In that case the value is
    plain text and must not prevent the containing table from loading.
    """
    if not isinstance(value, str):
        return value

    stripped_value = value.strip()
    if not stripped_value.startswith(_JSON_PREFIXES):
        return value

    try:
        return json.loads(stripped_value)
    except _JSON_PARSE_EXCEPTIONS:
        return value
