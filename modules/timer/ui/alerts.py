from __future__ import annotations

import tkinter as tk


class TimerAlerts:
    """Sound alerts for finished timers."""

    def __init__(self, parent: tk.Misc, sound_enabled: bool = True) -> None:
        self._parent = parent
        self._sound_enabled = bool(sound_enabled)

    def set_sound_enabled(self, enabled: bool) -> None:
        self._sound_enabled = bool(enabled)

    def notify_finished(self, timer_name: str) -> None:
        _ = timer_name
        if self._sound_enabled:
            self._play_sound()

    def _play_sound(self) -> None:
        try:
            self._parent.bell()
        except Exception:
            pass
