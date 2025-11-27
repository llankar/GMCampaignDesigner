"""Utilities for importing random tables from plain text definitions."""

import re
from typing import List


class RandomTableImportError(ValueError):
    """Raised when a random table import string cannot be parsed."""


def parse_random_table_text(raw_text: str) -> List[dict]:
    """Parse raw text rows into random table entries.

    Expected format per line: ``X-X Name Description`` where ``X-X`` is the
    numeric range, ``Name`` is the entry label, and ``Description`` is free
    text. Blank lines are ignored.
    """

    entries: List[dict] = []
    for line in (raw_text or "").splitlines():
        stripped = line.strip()
        if not stripped:
            continue

        match = re.match(r"^(?P<min>\d+)\s*-\s*(?P<max>\d+)\s+(?P<rest>.+)$", stripped)
        if not match:
            raise RandomTableImportError(
                "Each line must follow the pattern 'X-X Name Description'."
            )

        min_val = int(match.group("min"))
        max_val = int(match.group("max"))
        if min_val > max_val:
            raise RandomTableImportError("Min value cannot exceed max value.")

        rest = match.group("rest").strip()
        name, description = _split_name_and_description(rest)
        result_text = f"{name} - {description}" if description else name

        entries.append({"min": min_val, "max": max_val, "result": result_text, "tags": []})

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


__all__ = ["parse_random_table_text", "RandomTableImportError"]
