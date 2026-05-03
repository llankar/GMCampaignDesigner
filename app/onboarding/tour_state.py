from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class TourStateStore:
    """Simple JSON persistence for onboarding preferences and completion state."""

    def __init__(self, storage_path: str | Path = "config/onboarding_state.json") -> None:
        self._storage_path = Path(storage_path)
        self._state = self._load()

    def is_tour_completed(self, tour_id: str) -> bool:
        completed = self._state.get("completed_tours", [])
        return tour_id in completed

    def mark_tour_completed(self, tour_id: str) -> None:
        completed = set(self._state.get("completed_tours", []))
        completed.add(tour_id)
        self._state["completed_tours"] = sorted(completed)
        self.save()

    def is_auto_launch_enabled(self) -> bool:
        return bool(self._state.get("auto_launch_onboarding", True))

    def set_auto_launch_enabled(self, enabled: bool) -> None:
        self._state["auto_launch_onboarding"] = bool(enabled)
        self.save()

    def save(self) -> None:
        self._storage_path.parent.mkdir(parents=True, exist_ok=True)
        self._storage_path.write_text(json.dumps(self._state, indent=2), encoding="utf-8")

    def _load(self) -> dict[str, Any]:
        if not self._storage_path.exists():
            return {"completed_tours": [], "auto_launch_onboarding": True}
        try:
            raw_state = json.loads(self._storage_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"completed_tours": [], "auto_launch_onboarding": True}

        if not isinstance(raw_state, dict):
            return {"completed_tours": [], "auto_launch_onboarding": True}

        raw_state.setdefault("completed_tours", [])
        raw_state.setdefault("auto_launch_onboarding", True)
        return raw_state
