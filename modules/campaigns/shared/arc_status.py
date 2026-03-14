from __future__ import annotations

CANONICAL_ARC_STATUSES = ("Planned", "In Progress", "Paused", "Completed")
DEFAULT_ARC_STATUS = "Planned"

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


def canonicalize_arc_status(raw_status: object, default: str = DEFAULT_ARC_STATUS) -> str:
    text = str(raw_status or "").strip()
    if not text:
        return default
    return _STATUS_ALIASES.get(text.lower(), default)

