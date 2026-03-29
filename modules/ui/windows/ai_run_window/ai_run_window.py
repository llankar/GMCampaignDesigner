from __future__ import annotations

import customtkinter as ctk

from modules.core.ai.state.request_state import AIRequestState
from modules.helpers.window_helper import position_window_at_top
from .viewmodel import AIRunWindowViewModel
from .widgets.prompt_response_panel import PromptResponsePanel
from .widgets.step_timeline import StepTimeline


class AIRunWindow(ctk.CTkToplevel):
    def __init__(self, master, on_close_requested):
        super().__init__(master)
        self._on_close_requested = on_close_requested
        self.title("AI Run")
        self.geometry("760x620")
        self.resizable(True, True)

        self._phase_var = ctk.StringVar(value="Idle")
        self._status_var = ctk.StringVar(value="Waiting")

        ctk.CTkLabel(self, text="AI Pipeline", font=("Arial", 16, "bold")).pack(anchor="w", padx=16, pady=(16, 8))
        ctk.CTkLabel(self, textvariable=self._phase_var).pack(anchor="w", padx=16, pady=(0, 4))
        ctk.CTkLabel(self, textvariable=self._status_var).pack(anchor="w", padx=16, pady=(0, 8))

        self.timeline = StepTimeline(self, height=160)
        self.timeline.pack(fill="x", padx=16, pady=(0, 8))

        self.prompt_response_panel = PromptResponsePanel(self)
        self.prompt_response_panel.pack(fill="both", expand=True, padx=16, pady=(0, 12))

        ctk.CTkButton(self, text="Close", command=self._on_close).pack(anchor="e", padx=16, pady=(0, 12))
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.transient(master)
        position_window_at_top(self)

    def _on_close(self):
        self.withdraw()
        if callable(self._on_close_requested):
            self._on_close_requested()

    def show(self) -> None:
        self.deiconify()
        self.lift()
        self.attributes("-topmost", True)
        self.after_idle(lambda: self.attributes("-topmost", False))

    def render(self, state: AIRequestState) -> None:
        self.title(AIRunWindowViewModel.title(state))
        self._phase_var.set(AIRunWindowViewModel.phase_text(state))
        self._status_var.set(f"Status: {state.status}")
        self.timeline.render_items(state.timeline)
        self.prompt_response_panel.render(state)
