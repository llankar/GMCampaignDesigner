from __future__ import annotations

from typing import Callable

import customtkinter as ctk

from modules.scenarios.gm_screen.dashboard.styles.dashboard_theme import DASHBOARD_THEME
from .pill import OutlinedPill
from .scenario_metrics import ScenarioMetricChip, ScenarioTagRow


class ScenarioHeroStrip(ctk.CTkFrame):
    def __init__(
        self,
        parent,
        *,
        title: str,
        subtitle: str,
        count_chips: list[tuple[str, str]],
        on_edit: Callable[[], None],
        on_open_gm_screen: Callable[[], None] | None = None,
        accent: str | None = None,
    ):
        accent = accent or DASHBOARD_THEME.accent
        super().__init__(parent, fg_color="#0e1728", corner_radius=24, border_width=1, border_color="#243a5c")
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0)

        identity = ctk.CTkFrame(self, fg_color="transparent")
        identity.grid(row=0, column=0, sticky="nsew", padx=(18, 10), pady=18)
        identity.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            identity,
            text="Selected scenario".upper(),
            text_color="#8fb0dd",
            font=ctk.CTkFont(size=10, weight="bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(
            identity,
            text=title,
            text_color=DASHBOARD_THEME.text_primary,
            font=ctk.CTkFont(size=28, weight="bold"),
            anchor="w",
        ).grid(row=1, column=0, sticky="ew", pady=(4, 2))
        ctk.CTkLabel(
            identity,
            text=subtitle,
            text_color=DASHBOARD_THEME.text_secondary,
            font=ctk.CTkFont(size=13, weight="bold"),
            anchor="w",
        ).grid(row=2, column=0, sticky="w")

        chips = ctk.CTkFrame(identity, fg_color="transparent")
        chips.grid(row=3, column=0, sticky="w", pady=(12, 0))
        for index, (label, value) in enumerate(count_chips):
            OutlinedPill(
                chips,
                text=f"{value} {label}",
                text_color="#edf5ff",
                fg_color="#162742",
                border_color=accent,
                padx=12,
                pady=5,
                font=ctk.CTkFont(size=11, weight="bold"),
            ).grid(row=index // 4, column=index % 4, sticky="w", padx=(0, 8), pady=(0, 8))

        actions = ctk.CTkFrame(self, fg_color="#111f35", corner_radius=20)
        actions.grid(row=0, column=1, sticky="ne", padx=(10, 18), pady=18)
        actions.grid_columnconfigure(0, weight=1)
        ctk.CTkButton(
            actions,
            text="Edit scenario",
            command=on_edit,
            fg_color=accent,
            hover_color=DASHBOARD_THEME.accent_hover,
            width=164,
            height=38,
        ).grid(row=0, column=0, padx=14, pady=(14, 8), sticky="ew")
        ctk.CTkButton(
            actions,
            text="Open in GM screen",
            command=on_open_gm_screen,
            state="normal" if on_open_gm_screen else "disabled",
            fg_color="#1a2c46",
            hover_color="#223a5f",
            border_width=1,
            border_color="#33537f",
            width=164,
            height=38,
        ).grid(row=1, column=0, padx=14, pady=(0, 14), sticky="ew")


class ScenarioIdentityPanel(ctk.CTkFrame):
    def __init__(
        self,
        parent,
        *,
        eyebrow: str,
        title: str,
        summary: str,
        tags: list[str],
        progress_items: list[tuple[str, str]],
        on_edit: Callable[[], None],
        on_open_gm_screen: Callable[[], None] | None = None,
    ):
        super().__init__(parent, fg_color="#0d1728", corner_radius=20, border_width=1, border_color="#22395d")
        self.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            self,
            text=eyebrow.upper(),
            text_color="#8fb0dd",
            font=ctk.CTkFont(size=10, weight="bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="w", padx=16, pady=(16, 4))
        ctk.CTkLabel(
            self,
            text=title,
            text_color=DASHBOARD_THEME.text_primary,
            font=ctk.CTkFont(size=20, weight="bold"),
            anchor="w",
        ).grid(row=1, column=0, sticky="ew", padx=16)
        ctk.CTkLabel(
            self,
            text=summary,
            text_color=DASHBOARD_THEME.text_secondary,
            font=ctk.CTkFont(size=12),
            justify="left",
            wraplength=460,
            anchor="w",
        ).grid(row=2, column=0, sticky="ew", padx=16, pady=(10, 12))

        if tags:
            ScenarioTagRow(self, tags=tags[:6], accent="#33537f").grid(row=3, column=0, sticky="w", padx=16, pady=(0, 8))

        metrics = ctk.CTkFrame(self, fg_color="transparent")
        metrics.grid(row=4, column=0, sticky="ew", padx=16, pady=(4, 8))
        for index, (label, value) in enumerate(progress_items):
            ScenarioMetricChip(metrics, label=label, value=value, accent="#7dd3fc").grid(
                row=index // 2,
                column=index % 2,
                sticky="ew",
                padx=(0, 10),
                pady=(0, 10),
            )
            metrics.grid_columnconfigure(index % 2, weight=1)

        actions = ctk.CTkFrame(self, fg_color="transparent")
        actions.grid(row=5, column=0, sticky="w", padx=16, pady=(0, 16))
        ctk.CTkButton(
            actions,
            text="Edit scenario",
            command=on_edit,
            fg_color=DASHBOARD_THEME.accent,
            hover_color=DASHBOARD_THEME.accent_hover,
            width=134,
        ).grid(row=0, column=0, padx=(0, 8))
        ctk.CTkButton(
            actions,
            text="Open in GM screen",
            command=on_open_gm_screen,
            state="normal" if on_open_gm_screen else "disabled",
            fg_color="#17263d",
            hover_color="#223a5f",
            border_width=1,
            border_color="#33537f",
            width=148,
        ).grid(row=0, column=1)
