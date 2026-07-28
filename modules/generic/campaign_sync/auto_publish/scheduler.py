"""Pure idle-debounce and maximum-age scheduling decisions."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PublicationScheduler:
    idle_delay: float = 30.0
    maximum_interval: float = 300.0

    def __post_init__(self) -> None:
        if self.idle_delay < 0 or self.maximum_interval <= 0:
            raise ValueError("publication intervals must be positive")

    def due_at(self, first_dirty_at: float, last_dirty_at: float) -> float:
        return min(last_dirty_at + self.idle_delay, first_dirty_at + self.maximum_interval)

    def is_due(self, first_dirty_at: float, last_dirty_at: float, now: float) -> bool:
        return now >= self.due_at(first_dirty_at, last_dirty_at)
