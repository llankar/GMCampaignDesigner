from __future__ import annotations

from typing import List, Optional

import customtkinter as ctk

from modules.timer import get_timer_service
from modules.timer.models import TimerState
from modules.timer.ui.alerts import TimerAlerts
from modules.timer.ui.windows.control_window import TimerControlWindow
from modules.timer.ui.windows.display_window import TimerDisplayWindow
from modules.timer.ui.windows.time_format import format_seconds, parse_time_to_seconds


class TimerWindow:
    """Coordinates a compact control window + transparent display window."""

    def __init__(self, parent):
        self._parent = parent
        self._timer_service = get_timer_service(scheduler=parent)
        self._timer_id: Optional[str] = None
        self._last_duration_seconds: float = 300.0
        self._alerts = TimerAlerts(parent, sound_enabled=True)

        self._timer_service.subscribe(self._on_timers_changed)
        self._timer_service.subscribe_finished(self._on_timer_finished)

        self.control = TimerControlWindow(
            parent,
            on_start=self._start,
            on_stop=self._stop,
            on_pause=self._pause,
            on_continue=self._continue,
            on_remove_minute=lambda: self._adjust(-60),
            on_add_minute=lambda: self._adjust(60),
            on_close=self._close_control,
        )
        self.display = TimerDisplayWindow(parent)
        self.display.hide()

    def show(self) -> None:
        self.control.show()

    def _close_control(self) -> None:
        self.control.withdraw()

    def _ensure_timer(self) -> Optional[TimerState]:
        if self._timer_id:
            for timer in self._timer_service.list_timers():
                if timer.id == self._timer_id:
                    return timer

        timer = self._timer_service.create_timer(name="Timer MJ", mode="countdown", duration=self._last_duration_seconds)
        self._timer_id = timer.id
        return timer

    def _start(self) -> None:
        duration = parse_time_to_seconds(self.control.time_var.get(), fallback=self._last_duration_seconds)
        self._last_duration_seconds = duration
        timer = self._ensure_timer()
        if timer is None:
            return

        self._timer_service.delete_timer(timer.id)
        timer = self._timer_service.create_timer(name="Timer MJ", mode="countdown", duration=duration)
        self._timer_id = timer.id
        self._timer_service.start(timer.id)

        self.display.stop_finished_blink()
        self.control.withdraw()
        self.display.show()

    def _stop(self) -> None:
        timer = self._ensure_timer()
        if not timer:
            return
        self._timer_service.stop(timer.id)
        self._timer_service.reset(timer.id)
        self.display.stop_finished_blink()
        self.display.hide()

    def _pause(self) -> None:
        timer = self._ensure_timer()
        if timer:
            self._timer_service.pause(timer.id)

    def _continue(self) -> None:
        timer = self._ensure_timer()
        if timer:
            self._timer_service.resume(timer.id)
            self.display.show()

    def _adjust(self, seconds: float) -> None:
        timer = self._ensure_timer()
        if not timer:
            return
        if seconds >= 0:
            self._timer_service.add_time(timer.id, seconds)
        else:
            self._timer_service.subtract_time(timer.id, abs(seconds))

    def _on_timers_changed(self, timers: List[TimerState]) -> None:
        timer = None
        if self._timer_id:
            timer = next((item for item in timers if item.id == self._timer_id), None)
        if not timer:
            return
        if timer.mode == "countdown" and timer.running and timer.remaining > 0:
            self.display.stop_finished_blink()
        text = format_seconds(timer.remaining)
        self.display.set_time(text)
        self.control.time_var.set(text)


    def _on_timer_finished(self, timer: TimerState) -> None:
        if timer.id != self._timer_id:
            return
        self.display.show()
        self.display.start_finished_blink()
        self._alerts.notify_finished(timer.name)

    def destroy(self) -> None:
        self._timer_service.unsubscribe(self._on_timers_changed)
        self._timer_service.unsubscribe_finished(self._on_timer_finished)
        for window in (self.control, self.display):
            if isinstance(window, ctk.CTkToplevel) and window.winfo_exists():
                window.destroy()
