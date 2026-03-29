from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable


@dataclass(slots=True)
class AIRequestState:
    request_id: str = ""
    status: str = "idle"
    phase: str = ""
    phase_text: str = "Idle"
    window_visibility: str = "hidden"
    active: bool = False
    has_recent: bool = False
    auto_close_on_success_seconds: int = 0
    timeline: list[dict] = field(default_factory=list)


class AIRequestStateStore:
    def __init__(self) -> None:
        self._state = AIRequestState()
        self._listeners: list[Callable[[AIRequestState], None]] = []

    @property
    def state(self) -> AIRequestState:
        return self._state

    def subscribe(self, callback: Callable[[AIRequestState], None]) -> Callable[[], None]:
        self._listeners.append(callback)
        callback(self._state)

        def _unsubscribe() -> None:
            if callback in self._listeners:
                self._listeners.remove(callback)

        return _unsubscribe

    def update(self, **changes) -> None:
        for key, value in changes.items():
            setattr(self._state, key, value)
        self._notify()

    def append_timeline(self, item: dict) -> None:
        self._state.timeline.append(item)
        self._notify()

    def clear_timeline(self) -> None:
        self._state.timeline = []
        self._notify()

    def _notify(self) -> None:
        for callback in list(self._listeners):
            callback(self._state)


ai_request_state = AIRequestStateStore()
