"""State container for graph mode planner."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class GraphModeState:
    """Mutable planner state used by GraphModePlanner."""

    scenes: list[dict[str, Any]] = field(default_factory=list)

    def reset(self) -> None:
        self.scenes.clear()
