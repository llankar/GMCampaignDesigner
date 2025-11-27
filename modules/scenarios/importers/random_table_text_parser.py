"""Utilities for importing random tables from plain text definitions."""

import re
from typing import List


class RandomTableImportError(ValueError):
    """Raised when a random table import string cannot be parsed."""


def parse_random_table_text(raw_text: str) -> List[dict]:
    """Parse raw text rows into random table entries.

    Supported line patterns are intentionally permissive so common table
    formats work out of the box (e.g., table entries from SRD-style PDFs or
    blog posts). Blank lines are ignored.

    Examples of accepted formats:
    - ``1-3 Result text``
    - ``04–06: Result text`` (supports en dash and colon separator)
    - ``7 Result text``
    - ``12. Result text`` (period or parenthesis after the number is allowed)
    """

    entries: List[dict] = []
    for line in (raw_text or "").splitlines():
        stripped = line.strip()
        if not stripped:
            continue

        parsed = _parse_single_line(stripped)
        entries.append(parsed)

    if not entries:
        raise RandomTableImportError("No entries were found to import.")

    return entries


def _split_name_and_description(text: str) -> tuple[str, str]:
    if not text:
        return "", ""
    if " " not in text:
        return text, ""
    name, description = text.split(" ", 1)
    return name.strip(), description.strip()


def _parse_single_line(line: str) -> dict:
    match = re.match(
        r"^(?P<min>\d+)\s*[-–]\s*(?P<max>\d+)\s*[:.)-]?\s*(?P<rest>.+)$", line
    )
    if match:
        min_val = int(match.group("min"))
        max_val = int(match.group("max"))
        if min_val > max_val:
            raise RandomTableImportError("Min value cannot exceed max value.")
        rest = match.group("rest").strip()
        return _build_entry(min_val, max_val, rest)

    match = re.match(r"^(?P<value>\d+)\s*[:.)-]?\s*(?P<rest>.+)$", line)
    if match:
        value = int(match.group("value"))
        rest = match.group("rest").strip()
        return _build_entry(value, value, rest)

    raise RandomTableImportError(
        "Each line must start with a number or numeric range followed by text."
    )


def _build_entry(min_val: int, max_val: int, rest: str) -> dict:
    if not rest:
        raise RandomTableImportError("Entry text cannot be empty.")

    name, description = _split_name_and_description(rest)
    result_text = f"{name} - {description}" if description else name

    return {"min": min_val, "max": max_val, "result": result_text, "tags": []}


__all__ = ["parse_random_table_text", "RandomTableImportError"]
