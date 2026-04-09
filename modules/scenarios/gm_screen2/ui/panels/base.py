"""Base panel widget contract for GM Screen 2."""

from __future__ import annotations

import customtkinter as ctk

from modules.scenarios.gm_screen2.domain.models import PanelPayload


class BasePanelView(ctk.CTkFrame):
    """Passive panel view with a title and text body."""

    PANEL_KEY = "base"

    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self._title_label = ctk.CTkLabel(self, text="")
        self._title_label.pack(anchor="w", padx=8, pady=(8, 4))
        self._body_label = ctk.CTkLabel(self, text="", justify="left", anchor="nw")
        self._body_label.pack(fill="both", expand=True, padx=8, pady=(0, 8))

    def render_payload(self, payload: PanelPayload) -> None:
        """Render payload content without side effects."""
        self._title_label.configure(text=payload.title)
        self._body_label.configure(text="\n\n".join(payload.content_blocks))
