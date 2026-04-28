"""Formatting helpers for the compact audio bar."""

from __future__ import annotations

import os
from typing import Any

from modules.audio.audio_constants import SECTION_TITLES


def section_button_label(section: str) -> str:
    """Return the compact section label used by the toggle button."""
    if section == "effects":
        return "Sound"
    return SECTION_TITLES.get(section, section.title())


def track_identifier(track: dict[str, Any]) -> str:
    """Build a stable identifier for a track payload."""
    identifier = track.get("id")
    if identifier:
        return str(identifier)
    path = track.get("path")
    if isinstance(path, str) and path:
        return path
    return ""


def format_track_label(track: dict[str, Any]) -> str:
    """Return the user-facing label for a track."""
    name = track.get("name")
    if isinstance(name, str) and name:
        return name
    path = track.get("path")
    if isinstance(path, str) and path:
        return os.path.basename(path)
    return ""


def truncate_with_suffix(label: str, max_chars: int, suffix: str = "") -> str:
    """Truncate a label while preserving a suffix used for duplicate disambiguation."""
    suffix = suffix or ""
    if max_chars <= 0:
        return suffix[:max_chars]

    available = max_chars - len(suffix)
    if available <= 0:
        return suffix[:max_chars]

    if len(label) <= available:
        return label + suffix

    if available <= 1:
        truncated = label[:available]
    else:
        truncated = label[: available - 1].rstrip() + "…"

    return truncated + suffix


def make_dropdown_label(label: str, existing: set[str], max_chars: int) -> str:
    """Create a unique, width-constrained label for CTk option menus."""
    display = truncate_with_suffix(label, max_chars)
    if display not in existing:
        return display

    suffix_index = 2
    while True:
        suffix = f" ({suffix_index})"
        display = truncate_with_suffix(label, max_chars, suffix=suffix)
        if display not in existing:
            return display
        suffix_index += 1
