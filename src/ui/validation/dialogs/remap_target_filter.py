"""Filtering helpers for remap target selector dialogs."""

from __future__ import annotations

from collections.abc import Iterable


def filter_remap_target_display_values(
    display_values: Iterable[str],
    query: str,
) -> tuple[str, ...]:
    """Return display values matching all case-insensitive search terms."""

    values = tuple(display_values)
    normalized_query = str(query or "").strip().casefold()
    if not normalized_query:
        return values

    terms = tuple(term for term in normalized_query.split() if term)
    if not terms:
        return values

    return tuple(
        value
        for value in values
        if all(term in value.casefold() for term in terms)
    )
