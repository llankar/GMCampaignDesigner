"""The only auto-publication component allowed to call Tkinter APIs."""

from __future__ import annotations

import queue
from typing import Callable, Optional

from .models import WorkerEvent


class TkEventBridge:
    def __init__(self, root, events, on_event: Callable[[WorkerEvent], None], *, interval_ms: int = 100,
                 coordinator=None) -> None:
        self.root, self.events, self.on_event = root, events, on_event
        self.interval_ms, self.coordinator = max(10, interval_ms), coordinator
        self._after_id: Optional[str] = None
        self._running = False

    def start(self) -> None:
        if not self._running:
            self._running = True
            self._after_id = self.root.after(self.interval_ms, self._poll)

    def _poll(self) -> None:
        if not self._running:
            return
        while True:
            try:
                event = self.events.get_nowait()
            except queue.Empty:
                break
            if self.coordinator is not None:
                self.coordinator.handle_event(event)
            self.on_event(event)
        if self.coordinator is not None:
            self.coordinator.tick()
        if self._running:
            self._after_id = self.root.after(self.interval_ms, self._poll)

    def stop(self) -> None:
        self._running = False
        after_id, self._after_id = self._after_id, None
        if after_id is not None:
            try:
                self.root.after_cancel(after_id)
            except Exception:
                pass
