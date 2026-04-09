"""Docking drop-target metadata objects."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DropTarget:
    zone_id: str
    position: str
