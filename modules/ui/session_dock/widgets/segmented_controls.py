"""Segmented controls used by dock headers and panel filters."""

from __future__ import annotations

import customtkinter as ctk

from modules.ui.session_dock.theme.tokens import COLORS


class DockSegmentedControl(ctk.CTkSegmentedButton):
    """Themed segmented button preset."""

    def __init__(self, master: ctk.CTkBaseClass, values: list[str], command=None) -> None:
        super().__init__(
            master,
            values=values,
            command=command,
            fg_color=COLORS.background_subtle,
            selected_color=COLORS.accent_primary,
            selected_hover_color=COLORS.accent_primary_soft,
            unselected_color=COLORS.background_surface,
            unselected_hover_color=COLORS.background_subtle,
            text_color=COLORS.text_primary,
        )
