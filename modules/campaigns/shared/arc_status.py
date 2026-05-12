"""Shared status helpers for campaign arcs and scenarios."""
from __future__ import annotations

CANONICAL_ARC_STATUSES = ("Planned", "In Progress", "Paused", "Completed")
CANONICAL_SCENARIO_STATUSES = CANONICAL_ARC_STATUSES
CANONICAL_PROGRESS_STATUSES = CANONICAL_ARC_STATUSES

DEFAULT_ARC_STATUS = "Planned"
DEFAULT_SCENARIO_STATUS = DEFAULT_ARC_STATUS

_STATUS_ALIASES = {
    "planned": "Planned",
    "in progress": "In Progress",
    "progress": "In Progress",
    "running": "In Progress",
    "active": "In Progress",
    "paused": "Paused",
    "on hold": "Paused",
    "completed": "Completed",
    "complete": "Completed",
    "done": "Completed",
}


def canonicalize_progress_status(raw_status: object, default: str = DEFAULT_ARC_STATUS) -> str:
    """Return a canonical campaign progress status shared by arcs and scenarios."""
    text = str(raw_status or "").strip()
    if not text:
        return default
    return _STATUS_ALIASES.get(text.lower(), default)


def canonicalize_arc_status(raw_status: object, default: str = DEFAULT_ARC_STATUS) -> str:
    """Return a canonical arc status."""
    return canonicalize_progress_status(raw_status, default=default)


def canonicalize_scenario_status(raw_status: object, default: str = DEFAULT_SCENARIO_STATUS) -> str:
    """Return a canonical scenario status."""
    return canonicalize_progress_status(raw_status, default=default)
