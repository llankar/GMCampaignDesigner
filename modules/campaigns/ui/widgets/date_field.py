"""Field helpers for campaign date."""

from __future__ import annotations

import customtkinter as ctk

from modules.events.ui.shared.schedule_widgets import EventDatePickerField
from modules.generic.editor.styles import EDITOR_PALETTE, primary_button_style, toolbar_entry_style


class CampaignDateField(ctk.CTkFrame):
    """Labeled campaign date input with integrated calendar picker."""

    def __init__(self, master, *, label: str, initial_value: str = ""):
        """Initialize the CampaignDateField instance."""
        super().__init__(master, fg_color="transparent")
        self.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(self, text=label, text_color=EDITOR_PALETTE["text"]).grid(row=0, column=0, sticky="w", pady=(0, 4))
        self.picker = EventDatePickerField(
            self,
            initial_value=initial_value,
            entry_style=toolbar_entry_style(),
            button_style=primary_button_style(),
            clear_button_style={
                "border_width": 0,
                "text_color": EDITOR_PALETTE["text"],
                "hover_color": EDITOR_PALETTE["surface_soft"],
            },
            hint_text_color=EDITOR_PALETTE["muted_text"],
        )
        self.picker.grid(row=1, column=0, sticky="ew")

    def get(self) -> str:
        """Return the operation."""
        return self.picker.get()

    def set(self, value) -> None:
        """Set the operation."""
        self.picker.set(value)
