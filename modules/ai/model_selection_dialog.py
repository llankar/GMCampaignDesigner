"""Reusable CustomTkinter dialog for selecting a local AI model."""

from __future__ import annotations

from tkinter import messagebox

import customtkinter as ctk

from modules.helpers.config_helper import ConfigHelper
from modules.helpers.window_helper import position_window_at_top


class AIModelSelectionDialog(ctk.CTkToplevel):
    """Modal dialog allowing the user to pick one available AI model."""

    def __init__(self, master, models: list[str], *, title: str = "Select AI Model") -> None:
        """Initialize the AIModelSelectionDialog instance."""
        super().__init__(master)
        self.title(title)
        self.geometry("420x180")
        self.resizable(False, False)
        self.selected_model: str | None = None
        self._models = list(models or [])

        last_model = ConfigHelper.get("LastUsed", "scenario_ai_model", fallback=None)
        default_model = last_model if last_model in self._models else (self._models[0] if self._models else "")
        self.model_var = ctk.StringVar(value=default_model)

        self._build_ui()
        self.transient(master)
        self.grab_set()
        position_window_at_top(self)
        self.wait_window(self)

    def _build_ui(self) -> None:
        """Build dialog widgets."""
        frame = ctk.CTkFrame(self)
        frame.pack(fill="both", expand=True, padx=16, pady=16)

        label = ctk.CTkLabel(
            frame,
            text="Choose the Ollama model to use for this scenario generation:",
            anchor="w",
            wraplength=360,
        )
        label.pack(fill="x", pady=(0, 10))

        option = ctk.CTkOptionMenu(frame, values=self._models, variable=self.model_var)
        option.pack(fill="x", pady=(0, 16))

        buttons = ctk.CTkFrame(frame, fg_color="transparent")
        buttons.pack(fill="x")

        ctk.CTkButton(buttons, text="Cancel", command=self.destroy).pack(side="right", padx=(8, 0))
        ctk.CTkButton(buttons, text="Use Model", command=self._confirm).pack(side="right")

    def _confirm(self) -> None:
        """Confirm the current model selection."""
        model = self.model_var.get().strip()
        if not model:
            messagebox.showwarning("No model selected", "Please select a model before generating.")
            return
        ConfigHelper.set("LastUsed", "scenario_ai_model", model)
        self.selected_model = model
        self.destroy()
