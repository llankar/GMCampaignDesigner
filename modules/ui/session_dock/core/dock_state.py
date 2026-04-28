"""State model and persistence helpers for the session dock."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Literal

DockMode = Literal["hidden", "compact", "full"]
DockEdge = Literal["left", "right", "top", "bottom"]


@dataclass(slots=True)
class DockState:
    """Serializable dock state used across sessions."""

    mode: DockMode = "hidden"
    pinned_edge: DockEdge = "right"
    opacity: float = 0.96

    @classmethod
    def from_dict(cls, data: dict) -> "DockState":
        """Build and sanitize state from raw JSON data."""
        mode = data.get("mode", "hidden")
        edge = data.get("pinned_edge", "right")
        opacity = data.get("opacity", 0.96)

        if mode not in {"hidden", "compact", "full"}:
            mode = "hidden"
        if edge not in {"left", "right", "top", "bottom"}:
            edge = "right"
        try:
            normalized_opacity = float(opacity)
        except (TypeError, ValueError):
            normalized_opacity = 0.96
        normalized_opacity = max(0.35, min(1.0, normalized_opacity))

        return cls(mode=mode, pinned_edge=edge, opacity=normalized_opacity)

    def to_dict(self) -> dict:
        """Return plain JSON-safe representation."""
        return asdict(self)


class DockStateStore:
    """Disk-backed state persistence for dock configuration."""

    def __init__(self, state_file: Path | None = None) -> None:
        default_dir = Path.home() / ".gmcampaigndesigner"
        self._state_file = state_file or (default_dir / "session_dock_state.json")

    def load(self) -> DockState:
        """Load persisted state or return defaults."""
        if not self._state_file.exists():
            return DockState()

        try:
            raw = json.loads(self._state_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return DockState()

        return DockState.from_dict(raw if isinstance(raw, dict) else {})

    def save(self, state: DockState) -> None:
        """Persist state to disk."""
        self._state_file.parent.mkdir(parents=True, exist_ok=True)
        self._state_file.write_text(
            json.dumps(state.to_dict(), indent=2, sort_keys=True),
            encoding="utf-8",
        )
