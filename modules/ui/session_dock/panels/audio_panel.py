"""Session dock audio panel styled with shared session-dock tokens."""

from __future__ import annotations

import customtkinter as ctk

from modules.ui.session_dock.theme.component_styles import (
    ANIMATION_STYLE,
    BODY_LABEL_STYLE,
    PANEL_BASE_STYLE,
    TITLE_LABEL_STYLE,
    button_style,
    icon_style,
    spacing,
)


class AudioPanel(ctk.CTkFrame):
    """Compact audio controls for the session dock."""

    def __init__(self, master: ctk.CTkBaseClass, **kwargs) -> None:
        merged = {**PANEL_BASE_STYLE, **kwargs}
        super().__init__(master, **merged)

        pad = spacing("md")
        self.grid_columnconfigure(0, weight=1)

        self.title = ctk.CTkLabel(self, text="Audio", **TITLE_LABEL_STYLE)
        self.title.grid(row=0, column=0, sticky="w", padx=pad, pady=(pad, spacing("xs")))

        self.subtitle = ctk.CTkLabel(self, text="Ambiance and cues", **BODY_LABEL_STYLE)
        self.subtitle.grid(row=1, column=0, sticky="w", padx=pad, pady=(0, spacing("sm")))

        self.play_button = ctk.CTkButton(self, text="Play", **button_style("idle"))
        self.play_button.grid(row=2, column=0, sticky="ew", padx=pad, pady=(0, spacing("xs")))

        self.stop_button = ctk.CTkButton(self, text="Stop", **button_style("critical"))
        self.stop_button.grid(row=3, column=0, sticky="ew", padx=pad, pady=(0, pad))

        self.icon_token = icon_style("idle")
        self.timings = ANIMATION_STYLE.copy()

    def get_animation_timings(self) -> dict[str, int]:
        """Provide animation timings used by panel transitions."""
        return self.timings.copy()
