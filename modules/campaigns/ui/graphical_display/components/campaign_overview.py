from __future__ import annotations

import customtkinter as ctk

from modules.scenarios.gm_screen.dashboard.styles.dashboard_theme import DASHBOARD_THEME
from modules.scenarios.gm_screen.dashboard.widgets.arc_display.arc_momentum_meter import ArcMomentumMeter
from ..data import CampaignGraphPayload


class CampaignOverviewHero(ctk.CTkFrame):
    """Compact campaign summary header used by the graphical overview."""

    def __init__(
        self,
        parent,
        *,
        payload: CampaignGraphPayload,
        campaign_var,
        campaign_values: list[str],
        on_campaign_selected,
    ):
        super().__init__(parent, fg_color="#10192b", corner_radius=22, border_width=1, border_color="#223554")
        self._payload = payload
        self._campaign_var = campaign_var
        self._campaign_values = campaign_values
        self._on_campaign_selected = on_campaign_selected

        self.grid_columnconfigure(0, weight=3)
        self.grid_columnconfigure(1, weight=2)

        self._build_control_strip()
        self._build_identity_column()
        self._build_sidebar_column()


    def _build_control_strip(self) -> None:
        controls = ctk.CTkFrame(self, fg_color="transparent")
        controls.grid(row=0, column=0, columnspan=2, sticky="ew", padx=18, pady=(14, 0))
        controls.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            controls,
            text="Campaign overview",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=DASHBOARD_THEME.text_primary,
            anchor="w",
        ).grid(row=0, column=0, sticky="w")

        selector_wrap = ctk.CTkFrame(controls, fg_color="#16243b", corner_radius=14)
        selector_wrap.grid(row=0, column=1, sticky="e")
        selector_wrap.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            selector_wrap,
            text="Displayed campaign",
            text_color=DASHBOARD_THEME.text_secondary,
            font=ctk.CTkFont(size=11, weight="bold"),
        ).grid(row=0, column=0, sticky="w", padx=10, pady=(8, 1))

        ctk.CTkOptionMenu(
            selector_wrap,
            variable=self._campaign_var,
            values=self._campaign_values,
            command=self._on_campaign_selected,
            width=230,
            fg_color=DASHBOARD_THEME.input_bg,
            button_color=DASHBOARD_THEME.input_button,
            button_hover_color=DASHBOARD_THEME.input_hover,
            text_color=DASHBOARD_THEME.text_primary,
            dropdown_fg_color=DASHBOARD_THEME.card_bg,
            dropdown_hover_color=DASHBOARD_THEME.button_hover,
            dropdown_text_color=DASHBOARD_THEME.text_primary,
        ).grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 10))

    def _build_identity_column(self) -> None:
        identity = ctk.CTkFrame(self, fg_color="transparent")
        identity.grid(row=1, column=0, sticky="nsew", padx=(18, 12), pady=(12, 16))
        identity.grid_columnconfigure(0, weight=1)

        header = ctk.CTkFrame(identity, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew")
        header.grid_columnconfigure(1, weight=1)

        crest = ctk.CTkFrame(header, fg_color="#20123f", corner_radius=14, width=54, height=54)
        crest.grid(row=0, column=0, padx=(0, 12), sticky="n")
        crest.grid_propagate(False)
        ctk.CTkLabel(crest, text="✦", font=ctk.CTkFont(size=22, weight="bold"), text_color="#f7d774").place(relx=0.5, rely=0.38, anchor="center")
        ctk.CTkLabel(crest, text="GM", font=ctk.CTkFont(size=10, weight="bold"), text_color="#f3e8ff").place(relx=0.5, rely=0.72, anchor="center")

        title_wrap = ctk.CTkFrame(header, fg_color="transparent")
        title_wrap.grid(row=0, column=1, sticky="ew")
        title_wrap.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            title_wrap,
            text=self._payload.name,
            font=ctk.CTkFont(size=24, weight="bold"),
            text_color=DASHBOARD_THEME.text_primary,
            anchor="w",
        ).grid(row=0, column=0, sticky="ew")

        summary_text = self._payload.logline or self._payload.setting or self._payload.main_objective or "No campaign overview written yet."
        ctk.CTkLabel(
            title_wrap,
            text=summary_text,
            justify="left",
            text_color=DASHBOARD_THEME.text_secondary,
            anchor="w",
            wraplength=560,
        ).grid(row=1, column=0, sticky="ew", pady=(6, 0))

        chips = ctk.CTkFrame(identity, fg_color="transparent")
        chips.grid(row=1, column=0, sticky="w", pady=(12, 0))
        chip_index = 0
        for value in [self._payload.genre, self._payload.tone, self._payload.status]:
            if not value:
                continue
            _CompactChip(chips, text=value, fg_color="#1b3150", text_color="#d8ebff").grid(
                row=0,
                column=chip_index,
                padx=(0, 8),
            )
            chip_index += 1

        stats = ctk.CTkFrame(identity, fg_color="transparent")
        stats.grid(row=2, column=0, sticky="ew", pady=(12, 0))
        for column in range(3):
            stats.grid_columnconfigure(column, weight=1)

        stat_items = [
            ("Arcs", str(len(self._payload.arcs))),
            ("Scenarios", str(self._payload.linked_scenario_count)),
            ("Themes", _compact_count(self._payload.themes)),
        ]
        for column, (label, value) in enumerate(stat_items):
            _StatCard(stats, label=label, value=value).grid(row=0, column=column, sticky="ew", padx=(0 if column == 0 else 8, 0))

    def _build_sidebar_column(self) -> None:
        sidebar = ctk.CTkFrame(self, fg_color="transparent")
        sidebar.grid(row=1, column=1, sticky="nsew", padx=(0, 18), pady=(12, 16))
        for column in range(2):
            sidebar.grid_columnconfigure(column, weight=1)

        progress = ctk.CTkFrame(sidebar, fg_color="#120f28", corner_radius=18)
        progress.grid(row=0, column=0, rowspan=2, sticky="nsew", padx=(0, 10))
        ArcMomentumMeter(
            progress,
            completed_steps=sum(1 for arc in self._payload.arcs if arc.status.lower() == "completed"),
            total_steps=max(len(self._payload.arcs), 1),
            label="Arc completion",
        ).pack(padx=12, pady=(10, 6))
        ctk.CTkLabel(
            progress,
            text=f"{self._payload.linked_scenario_count} linked scenarios",
            justify="center",
            text_color=DASHBOARD_THEME.text_secondary,
            wraplength=120,
        ).pack(padx=8, pady=(0, 10))

        fact_items = [
            ("Setting", self._payload.setting),
            ("Objective", self._payload.main_objective),
            ("Stakes", self._payload.stakes),
            ("Themes", self._payload.themes),
        ]
        slot = 0
        for label, value in fact_items:
            if not value:
                continue
            row = slot // 2
            column = (slot % 2) + 1
            _FactTile(sidebar, label=label, value=value).grid(row=row, column=column, sticky="nsew", pady=(0, 10) if row == 0 else 0, padx=(0, 10) if column == 1 else 0)
            slot += 1


class _CompactChip(ctk.CTkFrame):
    def __init__(self, parent, *, text: str, fg_color: str, text_color: str):
        super().__init__(parent, fg_color=fg_color, corner_radius=999)
        ctk.CTkLabel(
            self,
            text=text,
            text_color=text_color,
            font=ctk.CTkFont(size=11, weight="bold"),
        ).pack(padx=12, pady=5)


class _StatCard(ctk.CTkFrame):
    def __init__(self, parent, *, label: str, value: str):
        super().__init__(parent, fg_color="#14233a", corner_radius=14, border_width=1, border_color="#223554")
        self.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            self,
            text=label.upper(),
            text_color="#8fb0dd",
            font=ctk.CTkFont(size=10, weight="bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="w", padx=12, pady=(8, 2))
        ctk.CTkLabel(
            self,
            text=value,
            text_color=DASHBOARD_THEME.text_primary,
            font=ctk.CTkFont(size=18, weight="bold"),
            anchor="w",
        ).grid(row=1, column=0, sticky="w", padx=12, pady=(0, 10))


class _FactTile(ctk.CTkFrame):
    def __init__(self, parent, *, label: str, value: str):
        super().__init__(parent, fg_color="#162239", corner_radius=14)
        self.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            self,
            text=label.upper(),
            text_color="#8fb0dd",
            font=ctk.CTkFont(size=10, weight="bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="w", padx=12, pady=(8, 1))
        ctk.CTkLabel(
            self,
            text=value,
            wraplength=220,
            justify="left",
            text_color=DASHBOARD_THEME.text_primary,
            anchor="w",
        ).grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 10))


def _compact_count(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return "0"
    return str(len([part for part in text.replace(";", ",").split(",") if part.strip()]))
