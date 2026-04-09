"""Event contracts for GM Screen 2 controller/view coordination."""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Callable

StateListener = Callable[[dict[str, Any]], None]


class EventBus:
    """Simple in-process pub/sub utility for screen events."""

    def __init__(self) -> None:
        self._listeners: dict[str, list[StateListener]] = defaultdict(list)

    def subscribe(self, event_name: str, callback: StateListener) -> None:
        """Register a callback for an event."""
        self._listeners[event_name].append(callback)

    def publish(self, event_name: str, payload: dict[str, Any] | None = None) -> None:
        """Trigger callbacks for an event."""
        event_payload = payload or {}
        for callback in list(self._listeners.get(event_name, [])):
            callback(event_payload)

    def clear(self) -> None:
        """Remove all listeners."""
        self._listeners.clear()
