"""Shared marker type metadata for map marker records."""

from __future__ import annotations

from dataclasses import dataclass


DEFAULT_MARKER_TYPE = "note"


@dataclass(frozen=True)
class MarkerType:
    key: str
    label: str
    color: str
    icon_path: str


MARKER_TYPES: tuple[MarkerType, ...] = (
    MarkerType("note", "Note", "#4FA3FF", "assets/icons/marker_note.png"),
    MarkerType("location", "Location", "#46C37B", "assets/icons/marker_location.png"),
    MarkerType("danger", "Danger", "#F35B5B", "assets/icons/marker_danger.png"),
    MarkerType("treasure", "Treasure", "#F2C94C", "assets/icons/marker_treasure.png"),
    MarkerType("quest", "Quest", "#B77BFF", "assets/icons/marker_quest.png"),
)

MARKER_TYPE_BY_KEY = {marker_type.key: marker_type for marker_type in MARKER_TYPES}
MARKER_TYPE_LABELS = [marker_type.label for marker_type in MARKER_TYPES]
MARKER_TYPE_LABEL_TO_KEY = {marker_type.label: marker_type.key for marker_type in MARKER_TYPES}
MARKER_TYPE_FILTER_LABELS = ["All Types", *MARKER_TYPE_LABELS]


def normalize_marker_type(value: object) -> str:
    """Return a known marker type key, preserving backward compatibility."""
    candidate = str(value or "").strip()
    if not candidate:
        return DEFAULT_MARKER_TYPE
    lowered = candidate.lower().replace(" ", "_")
    if lowered in MARKER_TYPE_BY_KEY:
        return lowered
    return MARKER_TYPE_LABEL_TO_KEY.get(candidate, DEFAULT_MARKER_TYPE)


def marker_type_label(value: object) -> str:
    """Return a user-facing marker type label."""
    marker_type = MARKER_TYPE_BY_KEY.get(normalize_marker_type(value))
    return marker_type.label if marker_type else MARKER_TYPE_BY_KEY[DEFAULT_MARKER_TYPE].label


def marker_type_icon_path(value: object) -> str:
    """Return the bundled icon path for a marker type."""
    marker_type = MARKER_TYPE_BY_KEY.get(normalize_marker_type(value))
    return marker_type.icon_path if marker_type else MARKER_TYPE_BY_KEY[DEFAULT_MARKER_TYPE].icon_path


def marker_type_color(value: object) -> str:
    """Return the display color for a marker type."""
    marker_type = MARKER_TYPE_BY_KEY.get(normalize_marker_type(value))
    return marker_type.color if marker_type else MARKER_TYPE_BY_KEY[DEFAULT_MARKER_TYPE].color
