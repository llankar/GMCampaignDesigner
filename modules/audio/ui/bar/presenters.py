"""Presentation helpers for AudioBarWindow dropdown data."""

from __future__ import annotations

from typing import Any

from .formatters import format_track_label, make_dropdown_label, track_identifier


def build_playlist_lookup(playlist: list[dict[str, Any]], max_chars: int) -> tuple[dict[str, dict[str, Any]], list[str]]:
    """Return lookup and values for the now-playing dropdown."""
    lookup: dict[str, dict[str, Any]] = {}
    values: list[str] = []
    existing_labels: set[str] = set()

    for index, track in enumerate(playlist):
        identifier = track_identifier(track)
        base_label = format_track_label(track) or f"Track {index + 1}"
        label = make_dropdown_label(base_label, existing_labels, max_chars)
        existing_labels.add(label)
        lookup[label] = {
            "identifier": identifier,
            "index": index,
            "track": track,
        }
        values.append(label)

    return lookup, values


def build_search_lookup(
    results: list[tuple[str, dict[str, Any]]],
    max_chars: int,
) -> tuple[dict[str, dict[str, Any]], list[str], str]:
    """Return lookup, dropdown values and placeholder for search results."""
    placeholder = f"{len(results)} result(s)"
    values = [placeholder]
    lookup: dict[str, dict[str, Any]] = {}
    existing_labels: set[str] = {placeholder}

    for label, info in results:
        display_label = make_dropdown_label(label, existing_labels, max_chars)
        existing_labels.add(display_label)
        enriched = dict(info)
        enriched["full_label"] = label
        lookup[display_label] = enriched
        values.append(display_label)

    return lookup, values, placeholder
