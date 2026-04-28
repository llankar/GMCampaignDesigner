"""Shared icon button wrapper for session dock controls."""

from __future__ import annotations

import customtkinter as ctk

from modules.ui.session_dock.theme.component_styles import button_style


class DockIconButton(ctk.CTkButton):
    """Small icon-like button with consistent dock styling."""

    def __init__(self, master: ctk.CTkBaseClass, text: str, command=None, state: str = "idle") -> None:
        super().__init__(
            master,
            text=text,
            width=34,
            height=30,
            corner_radius=8,
            border_width=1,
            command=command,
            **button_style(state),
        )
