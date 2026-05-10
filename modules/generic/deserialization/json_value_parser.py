"""Safe JSON value parsing for generic storage rows."""

from __future__ import annotations

import json
from typing import Any

from modules.generic.deserialization.json_candidates import looks_like_json_candidate

_RECOVERABLE_JSON_PARSE_ERRORS = (
    json.JSONDecodeError,
    TypeError,
    ValueError,
    StopIteration,
    RecursionError,
)


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
    if not looks_like_json_candidate(stripped_value):
        return value

    try:
        return json.loads(stripped_value)
    except _RECOVERABLE_JSON_PARSE_ERRORS:
        return value
