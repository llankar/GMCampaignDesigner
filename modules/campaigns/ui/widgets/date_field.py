from __future__ import annotations

import customtkinter as ctk

from modules.events.ui.shared.schedule_widgets import EventDatePickerField


class CampaignDateField(ctk.CTkFrame):
    """Labeled campaign date input with integrated calendar picker."""

    def __init__(self, master, *, label: str, initial_value: str = ""):
        super().__init__(master, fg_color="transparent")
        self.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(self, text=label).grid(row=0, column=0, sticky="w", pady=(0, 4))
        self.picker = EventDatePickerField(self, initial_value=initial_value)
        self.picker.grid(row=1, column=0, sticky="ew")

    def get(self) -> str:
        return self.picker.get()

    def set(self, value) -> None:
        self.picker.set(value)
