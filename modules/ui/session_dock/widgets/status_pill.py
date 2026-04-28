"""Tiny status pills for panel and service indicators."""

from __future__ import annotations

import customtkinter as ctk

from modules.ui.session_dock.theme.tokens import COLORS, STATES, TYPOGRAPHY

_COLORS = {
    "idle": STATES.idle,
    "success": STATES.success,
    "warning": STATES.warning,
    "critical": STATES.critical,
}


class StatusPill(ctk.CTkLabel):
    """Compact visual status token."""

    def __init__(self, master: ctk.CTkBaseClass, text: str, tone: str = "idle") -> None:
        super().__init__(
            master,
            text=text,
            corner_radius=999,
            fg_color=_COLORS.get(tone, STATES.idle),
            text_color=COLORS.background_canvas,
            font=(TYPOGRAPHY.font_family, TYPOGRAPHY.caption_size, TYPOGRAPHY.caption_weight),
            padx=8,
            pady=2,
        )
