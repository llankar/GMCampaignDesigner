"""Helpers that identify strings worth attempting to decode as JSON."""

from __future__ import annotations

_JSON_STRING_PREFIX = '"'
_JSON_CONTAINER_PAIRS = {
    "{": "}",
    "[": "]",
}
_JSON_ARRAY_VALUE_PREFIXES = frozenset('{["-0123456789tfn]')
_JSON_OBJECT_VALUE_PREFIXES = frozenset('"}')


def looks_like_json_candidate(value: str) -> bool:
    """Return whether ``value`` is plausible serialized JSON.

    User-authored notes sometimes start with JSON delimiter characters (for
    example ``[draft]`` or ``{idea``).  The generic loader should not ask the
    JSON decoder to parse obviously incomplete prose because those parse errors
    are expected plain-text content, not corrupt database rows.
    """

    stripped_value = value.strip()
    if not stripped_value:
        return False

    if stripped_value.startswith(_JSON_STRING_PREFIX):
        return True

    expected_suffix = _JSON_CONTAINER_PAIRS.get(stripped_value[0])
    if expected_suffix is None or not stripped_value.endswith(expected_suffix):
        return False

    return _has_plausible_container_content(stripped_value)


def _has_plausible_container_content(value: str) -> bool:
    """Return whether a bracketed value starts like JSON, not plain prose."""

    if value[0] == "[":
        return _first_inner_character(value) in _JSON_ARRAY_VALUE_PREFIXES

    if value[0] == "{":
        return _first_inner_character(value) in _JSON_OBJECT_VALUE_PREFIXES

    return False


def _first_inner_character(value: str) -> str:
    """Return the first non-whitespace character after the opening delimiter."""

    for character in value[1:]:
        if not character.isspace():
            return character
    return ""
