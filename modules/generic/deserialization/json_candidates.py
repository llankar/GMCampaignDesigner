"""Helpers that identify strings worth attempting to decode as JSON."""

from __future__ import annotations

_JSON_STRING_PREFIX = '"'
_JSON_CONTAINER_PAIRS = {
    "{": "}",
    "[": "]",
}


def looks_like_json_candidate(value: str) -> bool:
    """Return whether ``value`` is plausible serialized JSON.

    User-authored notes sometimes start with JSON delimiter characters (for
    example ``[draft]`` or ``{idea``).  The generic loader should not ask the
    JSON decoder to parse obviously incomplete text because those parse errors
    are expected plain-text content, not corrupt database rows.
    """

    stripped_value = value.strip()
    if not stripped_value:
        return False

    if stripped_value.startswith(_JSON_STRING_PREFIX):
        return True

    expected_suffix = _JSON_CONTAINER_PAIRS.get(stripped_value[0])
    if expected_suffix is None:
        return False

    return stripped_value.endswith(expected_suffix)
