from __future__ import annotations

import customtkinter as ctk

from modules.scenarios.gm_screen.dashboard.styles.dashboard_theme import DASHBOARD_THEME


class ScenarioBriefingPanel(ctk.CTkFrame):
    def __init__(self, parent, *, summary: str, objective: str = "", hook: str = "", stakes: str = ""):
        super().__init__(parent, fg_color="#0d1728", corner_radius=20, border_width=1, border_color="#22395d")
        self.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            self,
            text="Story briefing",
            text_color=DASHBOARD_THEME.text_primary,
            font=ctk.CTkFont(size=18, weight="bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="w", padx=16, pady=(16, 10))

        summary_block = ctk.CTkFrame(self, fg_color="#111f35", corner_radius=16, border_width=1, border_color="#2d476b")
        summary_block.grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 12))
        summary_block.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            summary_block,
            text="SUMMARY",
            text_color="#8fb0dd",
            font=ctk.CTkFont(size=10, weight="bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="w", padx=14, pady=(12, 4))
        ctk.CTkLabel(
            summary_block,
            text=summary or "No synopsis written yet for this scenario.",
            text_color=DASHBOARD_THEME.text_secondary,
            font=ctk.CTkFont(size=12),
            justify="left",
            wraplength=520,
            anchor="w",
        ).grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 14))

        row = 2
        for label, value, accent in (
            ("Objective", objective, "#7dd3fc"),
            ("Hook", hook, "#c084fc"),
            ("Stakes", stakes, "#fca5a5"),
        ):
            if not value:
                continue
            panel = ctk.CTkFrame(self, fg_color="#10192b", corner_radius=16, border_width=1, border_color="#243a5c")
            panel.grid(row=row, column=0, sticky="ew", padx=16, pady=(0, 10))
            panel.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(
                panel,
                text=label.upper(),
                text_color=accent,
                font=ctk.CTkFont(size=10, weight="bold"),
                anchor="w",
            ).grid(row=0, column=0, sticky="w", padx=14, pady=(11, 4))
            ctk.CTkLabel(
                panel,
                text=value,
                text_color=DASHBOARD_THEME.text_primary,
                font=ctk.CTkFont(size=12),
                justify="left",
                wraplength=520,
                anchor="w",
            ).grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 12))
            row += 1
