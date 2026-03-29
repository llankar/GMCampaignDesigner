from __future__ import annotations

import customtkinter as ctk

from modules.scenarios.gm_screen.dashboard.styles.dashboard_theme import DASHBOARD_THEME
from .pill import OutlinedPill


class ScenarioMetricChip(ctk.CTkFrame):
    def __init__(self, parent, *, label: str, value: str, accent: str = "#66c0ff"):
        super().__init__(parent, fg_color=DASHBOARD_THEME.card_bg, corner_radius=16, border_width=1, border_color=DASHBOARD_THEME.card_border)
        self.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            self,
            text=label.upper(),
            text_color=accent,
            font=ctk.CTkFont(size=10, weight="bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="w", padx=12, pady=(8, 2))
        ctk.CTkLabel(
            self,
            text=value,
            text_color=DASHBOARD_THEME.text_primary,
            font=ctk.CTkFont(size=15, weight="bold"),
            anchor="w",
        ).grid(row=1, column=0, sticky="w", padx=12, pady=(0, 10))


class ScenarioTagRow(ctk.CTkFrame):
    def __init__(self, parent, *, tags: list[str], accent: str = "#7dd3fc"):
        super().__init__(parent, fg_color="transparent")
        for index, tag in enumerate(tags):
            OutlinedPill(
                self,
                text=tag,
                text_color=DASHBOARD_THEME.text_primary,
                fg_color=DASHBOARD_THEME.button_fg,
                border_color=accent,
                font=ctk.CTkFont(size=11, weight="bold"),
            ).grid(row=index // 3, column=index % 3, sticky="w", padx=(0, 8), pady=(0, 8))
