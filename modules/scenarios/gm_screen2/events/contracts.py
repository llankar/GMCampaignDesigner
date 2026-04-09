"""Event contracts for GM Screen 2 controller/view coordination."""

from __future__ import annotations

from collections import defaultdict
from typing import Callable

StateListener = Callable[[], None]


class EventBus:
    """Simple in-process pub/sub utility for screen events."""

    def __init__(self) -> None:
        self._listeners: dict[str, list[StateListener]] = defaultdict(list)

    def subscribe(self, event_name: str, callback: StateListener) -> None:
        """Register a callback for an event."""
        self._listeners[event_name].append(callback)

    def publish(self, event_name: str) -> None:
        """Trigger callbacks for an event."""
        for callback in list(self._listeners.get(event_name, [])):
            callback()

    def clear(self) -> None:
        """Remove all listeners."""
        self._listeners.clear()
