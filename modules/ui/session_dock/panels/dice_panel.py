"""Dice panel rendered inside the session dock container."""

from __future__ import annotations

import customtkinter as ctk

from modules.ui.session_dock.theme.component_styles import BODY_LABEL_STYLE, PANEL_BASE_STYLE, TITLE_LABEL_STYLE, spacing
from modules.ui.session_dock.widgets import DockIconButton, DockSegmentedControl, StatusPill, attach_tooltip


class DicePanel(ctk.CTkFrame):
    """Quick roll controls for table actions."""

    panel_id = "dice"

    def __init__(self, master: ctk.CTkBaseClass, **kwargs) -> None:
        super().__init__(master, **{**PANEL_BASE_STYLE, **kwargs})
        pad = spacing("md")

        self.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(self, text="Dice", **TITLE_LABEL_STYLE).grid(
            row=0, column=0, sticky="w", padx=pad, pady=(pad, spacing("xs"))
        )
        StatusPill(self, text="Ready", tone="success").grid(row=0, column=1, sticky="e", padx=pad, pady=(pad, spacing("xs")))
        ctk.CTkLabel(self, text="Fast checks and rolls", **BODY_LABEL_STYLE).grid(
            row=1, column=0, columnspan=2, sticky="w", padx=pad, pady=(0, spacing("sm"))
        )

        modes = DockSegmentedControl(self, values=["d20", "d12", "d6"])
        modes.set("d20")
        modes.grid(row=2, column=0, columnspan=2, sticky="ew", padx=pad, pady=(0, spacing("sm")))

        roll = DockIconButton(self, text="🎲", state="active")
        clear = DockIconButton(self, text="⟲")
        roll.grid(row=3, column=0, sticky="w", padx=(pad, spacing("xs")), pady=(0, pad))
        clear.grid(row=3, column=1, sticky="w", padx=(0, pad), pady=(0, pad))
        attach_tooltip(roll, "Roll selected die")
        attach_tooltip(clear, "Clear result")
