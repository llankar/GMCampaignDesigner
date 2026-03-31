"""Utilities for timer alerts."""

from __future__ import annotations

import tkinter as tk


class TimerAlerts:
    """Sound alerts for finished timers."""

    def __init__(self, parent: tk.Misc, sound_enabled: bool = True) -> None:
        """Initialize the TimerAlerts instance."""
        self._parent = parent
        self._sound_enabled = bool(sound_enabled)

    def set_sound_enabled(self, enabled: bool) -> None:
        """Set sound enabled."""
        self._sound_enabled = bool(enabled)

    def notify_finished(self, timer_name: str) -> None:
        """Notify finished."""
        _ = timer_name
        if self._sound_enabled:
            self._play_sound()

    def _play_sound(self) -> None:
        """Internal helper for play sound."""
        try:
            self._parent.bell()
        except Exception:
            pass
