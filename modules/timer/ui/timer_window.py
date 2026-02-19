from __future__ import annotations

from typing import Dict, List, Optional

import customtkinter as ctk

from modules.timer import get_timer_service
from modules.timer.models import TimerPreset, TimerState
from modules.timer.ui.alerts import TimerAlerts
from modules.timer.ui.history_panel import HistoryPanel
from modules.timer.ui.presets_panel import PresetsPanel
from modules.timer.ui.overlay_style import (
    CLOCK_FONT,
    OVERLAY_ALPHA_FALLBACK,
    OVERLAY_BORDER_COLOR,
    OVERLAY_GEOMETRY,
    OVERLAY_TRANSPARENT_KEY,
    STATUS_FONT,
    TITLE_FONT,
)


class TimerWindow(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Session Timers")
        self.geometry(OVERLAY_GEOMETRY)
        self.minsize(360, 220)
        self.attributes("-topmost", True)
        self.configure(fg_color=OVERLAY_TRANSPARENT_KEY)
        self._apply_transparency()

        self._timer_service = get_timer_service(scheduler=parent)
        self._alerts = TimerAlerts(self)
        self._selected_timer_id: Optional[str] = None
        self._rendered_timers: Dict[str, ctk.CTkFrame] = {}

        self._build_layout()
        self._timer_service.subscribe(self._on_timers_changed)
        self._timer_service.subscribe_finished(self._on_timer_finished)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _apply_transparency(self) -> None:
        try:
            self.wm_attributes("-transparentcolor", OVERLAY_TRANSPARENT_KEY)
        except Exception:
            self.attributes("-alpha", OVERLAY_ALPHA_FALLBACK)

    def _build_layout(self) -> None:
        container = ctk.CTkFrame(self, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=6, pady=6)

        self._build_create_controls(container)
        self._build_actions(container)

        self._timers_scroll = ctk.CTkScrollableFrame(container, fg_color="transparent")
        self._timers_scroll.pack(fill="both", expand=True, padx=2, pady=(2, 4))

        self._queue_label = ctk.CTkLabel(container, text="Queue: none", anchor="w")
        self._queue_label.pack(fill="x", padx=4, pady=(0, 4))

        self._presets_panel = PresetsPanel(container, self._timer_service, self._create_from_preset)
        self._presets_panel.pack(fill="x", padx=2, pady=(0, 4))

        self._history_panel = HistoryPanel(container)
        self._history_panel.pack_forget()

    def _build_create_controls(self, parent) -> None:
        box = ctk.CTkFrame(parent, fg_color="transparent")
        box.pack(fill="x", padx=2, pady=(2, 2))

        self._new_name = ctk.StringVar(value="Timer")
        self._new_duration = ctk.StringVar(value="300")
        self._new_mode = ctk.StringVar(value="countdown")
        self._new_repeat = ctk.BooleanVar(value=False)

        ctk.CTkLabel(box, text="Create timer", font=("Segoe UI", 12, "bold")).pack(anchor="w", padx=4, pady=(2, 2))
        ctk.CTkEntry(box, textvariable=self._new_name, placeholder_text="Timer name").pack(fill="x", padx=4, pady=2)
        ctk.CTkEntry(box, textvariable=self._new_duration, placeholder_text="Duration (seconds)").pack(fill="x", padx=4, pady=2)
        ctk.CTkSegmentedButton(box, values=["countdown", "stopwatch"], variable=self._new_mode).pack(fill="x", padx=4, pady=2)
        ctk.CTkCheckBox(box, text="Repeat auto", variable=self._new_repeat).pack(anchor="w", padx=4, pady=2)
        ctk.CTkButton(box, text="Add timer", command=self._create_timer).pack(fill="x", padx=4, pady=(2, 2))

    def _build_actions(self, parent) -> None:
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=2, pady=(0, 2))

        buttons = [
            ("Start", self._start_selected),
            ("Pause", self._pause_selected),
            ("Resume", self._resume_selected),
            ("Stop", self._stop_selected),
            ("Reset", self._reset_selected),
            ("Lap", self._lap_selected),
            ("+30s", lambda: self._time_adjust_selected(30)),
            ("+1min", lambda: self._time_adjust_selected(60)),
            ("-1min", lambda: self._time_adjust_selected(-60)),
            ("Toggle Repeat", self._toggle_repeat_selected),
            ("Delete", self._delete_selected),
            ("Apply first preset", self._presets_panel_apply_first),
        ]
        for idx, (label, callback) in enumerate(buttons):
            btn = ctk.CTkButton(row, text=label, command=callback)
            btn.grid(row=idx // 4, column=idx % 4, sticky="ew", padx=2, pady=2)
        for col in range(4):
            row.grid_columnconfigure(col, weight=1)

    def _presets_panel_apply_first(self) -> None:
        self._presets_panel.apply_first()

    def _create_timer(self) -> None:
        try:
            duration = max(0.0, float(self._new_duration.get() or 0))
        except Exception:
            duration = 0.0
        timer = self._timer_service.create_timer(
            name=self._new_name.get().strip() or "Timer",
            mode=self._new_mode.get(),
            duration=duration,
            repeat=bool(self._new_repeat.get()),
        )
        self._selected_timer_id = timer.id

    def _create_from_preset(self, preset: TimerPreset) -> None:
        timer = self._timer_service.create_timer(
            name=preset.name,
            mode=preset.mode,
            duration=preset.duration,
            repeat=preset.repeat,
            color_tag=preset.color_tag,
        )
        self._selected_timer_id = timer.id

    def _selected_timer(self) -> Optional[TimerState]:
        if not self._selected_timer_id:
            return None
        for timer in self._timer_service.list_timers():
            if timer.id == self._selected_timer_id:
                return timer
        return None

    def _start_selected(self) -> None:
        timer = self._selected_timer()
        if timer:
            self._timer_service.start(timer.id)

    def _pause_selected(self) -> None:
        timer = self._selected_timer()
        if timer:
            self._timer_service.pause(timer.id)

    def _resume_selected(self) -> None:
        timer = self._selected_timer()
        if timer:
            self._timer_service.resume(timer.id)

    def _stop_selected(self) -> None:
        timer = self._selected_timer()
        if timer:
            self._timer_service.stop(timer.id)

    def _reset_selected(self) -> None:
        timer = self._selected_timer()
        if timer:
            self._timer_service.reset(timer.id)

    def _lap_selected(self) -> None:
        timer = self._selected_timer()
        if not timer:
            return
        value = self._timer_service.lap(timer.id)
        if value is not None:
            self._history_panel.add_lap(timer.name, value)

    def _time_adjust_selected(self, delta: float) -> None:
        timer = self._selected_timer()
        if not timer:
            return
        if delta >= 0:
            self._timer_service.add_time(timer.id, delta)
        else:
            self._timer_service.subtract_time(timer.id, abs(delta))

    def _toggle_repeat_selected(self) -> None:
        timer = self._selected_timer()
        if timer:
            self._timer_service.set_repeat(timer.id, not timer.repeat)

    def _delete_selected(self) -> None:
        timer = self._selected_timer()
        if timer and self._timer_service.delete_timer(timer.id):
            self._selected_timer_id = None

    def _on_timers_changed(self, timers: List[TimerState]) -> None:
        existing_ids = set(self._rendered_timers.keys())
        incoming_ids = {timer.id for timer in timers}

        for timer_id in existing_ids - incoming_ids:
            frame = self._rendered_timers.pop(timer_id)
            frame.destroy()

        for timer in timers:
            if timer.id not in self._rendered_timers:
                self._rendered_timers[timer.id] = self._build_timer_row(timer)
            self._update_timer_row(self._rendered_timers[timer.id], timer)

        next_timer = self._timer_service.next_in_queue()
        next_name = next_timer.name if next_timer else "none"
        self._queue_label.configure(text=f"Queue: {next_name}")
        self._presets_panel.refresh()

    def _build_timer_row(self, timer: TimerState) -> ctk.CTkFrame:
        frame = ctk.CTkFrame(self._timers_scroll, fg_color="transparent")
        frame.pack(fill="x", padx=2, pady=2)

        title = ctk.CTkLabel(frame, text=timer.name, font=TITLE_FONT)
        title.grid(row=0, column=0, sticky="w", padx=4, pady=(2, 0))

        status = ctk.CTkLabel(frame, text="", font=STATUS_FONT)
        status.grid(row=0, column=1, sticky="e", padx=4, pady=(2, 0))

        clock = ctk.CTkLabel(frame, text="00:00:00", font=CLOCK_FONT)
        clock.grid(row=1, column=0, columnspan=2, sticky="ew", padx=4, pady=(0, 2))

        frame.grid_columnconfigure(0, weight=1)
        frame.bind("<Button-1>", lambda _e, t_id=timer.id: self._select_timer(t_id))
        title.bind("<Button-1>", lambda _e, t_id=timer.id: self._select_timer(t_id))
        status.bind("<Button-1>", lambda _e, t_id=timer.id: self._select_timer(t_id))
        clock.bind("<Button-1>", lambda _e, t_id=timer.id: self._select_timer(t_id))

        frame._title = title
        frame._status = status
        frame._clock = clock
        return frame

    def _update_timer_row(self, frame: ctk.CTkFrame, timer: TimerState) -> None:
        frame._title.configure(text=f"{timer.name} ({timer.mode})")
        status = "running" if timer.running else "paused" if timer.paused else "stopped"
        repeat = " • repeat" if timer.repeat else ""
        frame._status.configure(text=f"{status}{repeat}")
        frame._clock.configure(text=self._format_seconds(timer.remaining))
        selected = timer.id == self._selected_timer_id
        frame.configure(border_width=2 if selected else 0, border_color=OVERLAY_BORDER_COLOR)

    def _select_timer(self, timer_id: str) -> None:
        self._selected_timer_id = timer_id
        self._on_timers_changed(self._timer_service.list_timers())

    def _on_timer_finished(self, timer: TimerState) -> None:
        self._history_panel.add_finished(timer.name)
        self._alerts.notify_finished(timer.name)

    def _on_close(self) -> None:
        self._timer_service.unsubscribe(self._on_timers_changed)
        self._timer_service.unsubscribe_finished(self._on_timer_finished)
        self.destroy()

    @staticmethod
    def _format_seconds(seconds: float) -> str:
        total = max(0, int(seconds))
        hours, rem = divmod(total, 3600)
        minutes, sec = divmod(rem, 60)
        return f"{hours:02d}:{minutes:02d}:{sec:02d}"
