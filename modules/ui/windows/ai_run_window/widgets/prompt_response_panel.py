from __future__ import annotations

import customtkinter as ctk

from modules.core.ai.state.request_state import AIRequestState
from modules.ui.windows.ai_run_window.formatters import (
    format_ai_prompt_for_humans,
    format_ai_response_for_humans,
)
from .raw_text_view import RawTextView


class PromptResponsePanel(ctk.CTkFrame):
    def __init__(self, master) -> None:
        super().__init__(master)
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self._tabs = ctk.CTkTabview(self)
        self._tabs.grid(row=0, column=0, sticky="nsew")

        prompt_tab = self._tabs.add("Prompt")
        response_tab = self._tabs.add("Response")

        for tab in (prompt_tab, response_tab):
            tab.grid_rowconfigure(0, weight=1)
            tab.grid_columnconfigure(0, weight=1)

        self._prompt_view = RawTextView(prompt_tab, empty_message="No data yet")
        self._prompt_view.grid(row=0, column=0, sticky="nsew")
        self._prompt_view.set_copy_label("Copy prompt")

        self._response_view = RawTextView(response_tab, empty_message="No data yet")
        self._response_view.grid(row=0, column=0, sticky="nsew")
        self._response_view.set_copy_label("Copy response")

    def render(self, state: AIRequestState) -> None:
        self._prompt_view.render_text(format_ai_prompt_for_humans(state.prompt_text))
        self._response_view.render_text(format_ai_response_for_humans(state.response_text))
