"""Audio panel rendered inside the session dock container."""

from __future__ import annotations

import customtkinter as ctk

from modules.ui.session_dock.theme.component_styles import BODY_LABEL_STYLE, PANEL_BASE_STYLE, TITLE_LABEL_STYLE, spacing
from modules.ui.session_dock.widgets import DockIconButton, StatusPill, attach_tooltip


class AudioPanel(ctk.CTkFrame):
    """Compact audio controls for ambience and cues."""

    panel_id = "audio"

    def __init__(self, master: ctk.CTkBaseClass, **kwargs) -> None:
        super().__init__(master, **{**PANEL_BASE_STYLE, **kwargs})
        pad = spacing("md")

        self.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(self, text="Audio", **TITLE_LABEL_STYLE).grid(
            row=0, column=0, sticky="w", padx=pad, pady=(pad, spacing("xs"))
        )
        StatusPill(self, text="Idle", tone="idle").grid(row=0, column=1, sticky="e", padx=pad, pady=(pad, spacing("xs")))
        ctk.CTkLabel(self, text="Ambience and cues", **BODY_LABEL_STYLE).grid(
            row=1, column=0, columnspan=2, sticky="w", padx=pad, pady=(0, spacing("sm"))
        )

        play = DockIconButton(self, text="▶")
        stop = DockIconButton(self, text="■", state="critical")
        play.grid(row=2, column=0, sticky="w", padx=(pad, spacing("xs")), pady=(0, pad))
        stop.grid(row=2, column=1, sticky="w", padx=(0, pad), pady=(0, pad))
        attach_tooltip(play, "Play ambience")
        attach_tooltip(stop, "Stop ambience")
