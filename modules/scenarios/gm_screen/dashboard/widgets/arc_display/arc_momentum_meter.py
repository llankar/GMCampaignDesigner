"""Utilities for arc display arc momentum meter."""

from __future__ import annotations

import tkinter as tk

import customtkinter as ctk

from modules.scenarios.gm_screen.dashboard.styles.dashboard_theme import DASHBOARD_THEME


class ArcMomentumMeter(ctk.CTkFrame):
    """Circular meter that highlights arc completion momentum."""

    def __init__(self, parent, *, completed_steps: int, total_steps: int, label: str):
        """Initialize the ArcMomentumMeter instance."""
        super().__init__(parent, fg_color="transparent")
        self.grid_columnconfigure(0, weight=1)

        total = max(total_steps, 1)
        progress = max(0.0, min(1.0, completed_steps / total))

        canvas_size = 90
        thickness = 10
        pad = 12
        self.canvas = tk.Canvas(
            self,
            width=canvas_size,
            height=canvas_size,
            bg=DASHBOARD_THEME.card_bg,
            highlightthickness=0,
            bd=0,
        )
        self.canvas.grid(row=0, column=0, padx=6, pady=(6, 2))

        arc_box = (pad, pad, canvas_size - pad, canvas_size - pad)
        self.canvas.create_arc(
            arc_box,
            start=135,
            extent=270,
            style="arc",
            outline=DASHBOARD_THEME.arc_track,
            width=thickness,
        )
        self.canvas.create_arc(
            arc_box,
            start=135,
            extent=270 * progress,
            style="arc",
            outline=DASHBOARD_THEME.accent_soft,
            width=thickness,
        )
        self.canvas.create_text(
            canvas_size / 2,
            canvas_size / 2,
            text=f"{round(progress * 100)}%",
            fill=DASHBOARD_THEME.text_primary,
            font=("Segoe UI", 11, "bold"),
        )

        ctk.CTkLabel(
            self,
            text=label,
            text_color=DASHBOARD_THEME.text_secondary,
            font=ctk.CTkFont(size=11),
        ).grid(row=1, column=0, padx=4, pady=(0, 4))
