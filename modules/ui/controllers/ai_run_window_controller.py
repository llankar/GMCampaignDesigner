from __future__ import annotations

from uuid import uuid4

from modules.core.ai.events import (
    AIPipelineEvent,
    EVENT_AI_PIPELINE_COMPLETED,
    EVENT_AI_PIPELINE_FAILED,
    EVENT_AI_PIPELINE_PHASE,
    EVENT_AI_PIPELINE_STARTED,
    ai_pipeline_events,
)
from modules.core.ai.state.request_state import ai_request_state
from modules.ui.windows.ai_run_window.ai_run_window import AIRunWindow


class AIRunWindowController:
    def __init__(self, app, menu_bar):
        self.app = app
        self.menu_bar = menu_bar
        self._window: AIRunWindow | None = None
        self._last_request_id = ""
        self._auto_close_job = None

        self._open_button = self.menu_bar.create_action_button(
            text="AI Run",
            command=self.open_window,
            width=80,
        )

        ai_pipeline_events.subscribe("*", self._on_pipeline_event)
        ai_request_state.subscribe(self._on_state_changed)

    def new_request_id(self) -> str:
        return uuid4().hex

    def open_window(self) -> None:
        window = self._ensure_window()
        window.show()
        ai_request_state.update(window_visibility="visible")

    def _ensure_window(self) -> AIRunWindow:
        if self._window is None or not self._window.winfo_exists():
            self._window = AIRunWindow(self.app, on_close_requested=self._on_close_requested)
        return self._window

    def _on_close_requested(self) -> None:
        ai_request_state.update(window_visibility="hidden")

    def _on_pipeline_event(self, event: AIPipelineEvent) -> None:
        if event.event_type == EVENT_AI_PIPELINE_STARTED:
            ai_request_state.clear_timeline()
            ai_request_state.update(
                request_id=event.request_id,
                status="running",
                phase=event.phase,
                phase_text=event.message or "Running",
                active=True,
                has_recent=True,
            )
            ai_request_state.append_timeline({"phase": event.phase or "Start", "message": event.message, "status": "active"})
            if ai_request_state.state.window_visibility == "hidden":
                self.open_window()
            return

        if event.event_type == EVENT_AI_PIPELINE_PHASE:
            timeline = ai_request_state.state.timeline
            if timeline:
                timeline[-1]["status"] = "done"
            ai_request_state.append_timeline({"phase": event.phase, "message": event.message, "status": "active"})
            ai_request_state.update(phase=event.phase, phase_text=event.message or event.phase)
            if ai_request_state.state.window_visibility == "hidden" and ai_request_state.state.active:
                self.open_window()
            return

        if event.event_type in (EVENT_AI_PIPELINE_COMPLETED, EVENT_AI_PIPELINE_FAILED):
            timeline = ai_request_state.state.timeline
            if timeline:
                timeline[-1]["status"] = "done" if event.event_type == EVENT_AI_PIPELINE_COMPLETED else "error"
            status = "completed" if event.event_type == EVENT_AI_PIPELINE_COMPLETED else "error"
            ai_request_state.update(
                status=status,
                phase=event.phase,
                phase_text=event.message or status,
                active=False,
                has_recent=True,
            )
            self.open_window()
            self._schedule_auto_close_if_needed(event.event_type == EVENT_AI_PIPELINE_COMPLETED)

    def _schedule_auto_close_if_needed(self, is_success: bool) -> None:
        if self._auto_close_job is not None:
            try:
                self.app.after_cancel(self._auto_close_job)
            except Exception:
                pass
            self._auto_close_job = None

        seconds = int(ai_request_state.state.auto_close_on_success_seconds or 0)
        if not is_success or seconds <= 0:
            return

        self._auto_close_job = self.app.after(seconds * 1000, self._auto_close)

    def _auto_close(self) -> None:
        self._auto_close_job = None
        if self._window and self._window.winfo_exists():
            self._window.withdraw()
            ai_request_state.update(window_visibility="hidden")

    def _on_state_changed(self, state):
        self._open_button.configure(text="AI Run*" if state.active else "AI Run")
        if self._window and self._window.winfo_exists():
            self._window.render(state)
