from __future__ import annotations

import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox

from modules.generic.entity_detail_factory import open_entity_tab
from modules.generic.generic_model_wrapper import GenericModelWrapper
from modules.scenarios.gm_screen.dashboard.styles.dashboard_theme import DASHBOARD_THEME
from modules.scenarios.gm_screen.dashboard.widgets.arc_display.arc_momentum_meter import ArcMomentumMeter

from .data import CampaignGraphArc, CampaignGraphPayload, build_campaign_graph_payload, build_campaign_option_index
from .visuals import ArcScenarioStrip, CapsuleWrap, EntityConstellation


class CampaignGraphPanel(ctk.CTkFrame):
    """RPG-forward campaign visualizer with campaign text, arcs, scenarios, and linked entities."""

    def __init__(self, master, *, campaign_wrapper=None, scenario_wrapper=None):
        super().__init__(master, fg_color=DASHBOARD_THEME.panel_bg)
        self.campaign_wrapper = campaign_wrapper or GenericModelWrapper("campaigns")
        self.scenario_wrapper = scenario_wrapper or GenericModelWrapper("scenarios")

        self._campaign_items = self._safe_load(self.campaign_wrapper)
        self._scenario_items = self._safe_load(self.scenario_wrapper)
        self._campaign_options, self._campaign_index = build_campaign_option_index(self._campaign_items)
        self._selected_campaign: CampaignGraphPayload | None = None

        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self._build_header()
        self._build_body()
        self._load_initial_campaign()

    def _build_header(self) -> None:
        header = ctk.CTkFrame(self, fg_color=DASHBOARD_THEME.panel_alt_bg, corner_radius=20)
        header.grid(row=0, column=0, sticky="ew", padx=16, pady=(16, 10))
        header.grid_columnconfigure(1, weight=1)

        crest = ctk.CTkFrame(header, fg_color="#20123f", corner_radius=18, width=86, height=86)
        crest.grid(row=0, column=0, rowspan=2, padx=(16, 12), pady=16)
        crest.grid_propagate(False)
        ctk.CTkLabel(crest, text="✦", font=ctk.CTkFont(size=34, weight="bold"), text_color="#f7d774").place(relx=0.5, rely=0.42, anchor="center")
        ctk.CTkLabel(crest, text="GM", font=ctk.CTkFont(size=12, weight="bold"), text_color="#f3e8ff").place(relx=0.5, rely=0.74, anchor="center")

        text_wrap = ctk.CTkFrame(header, fg_color="transparent")
        text_wrap.grid(row=0, column=1, sticky="ew", pady=(16, 8))
        text_wrap.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            text_wrap,
            text="Campaign Constellation",
            font=ctk.CTkFont(size=24, weight="bold"),
            text_color=DASHBOARD_THEME.text_primary,
            anchor="w",
        ).grid(row=0, column=0, sticky="w")

        ctk.CTkLabel(
            text_wrap,
            text="Read the campaign at a glance: lore, arcs, scenario flow, and clickable entity constellations.",
            font=ctk.CTkFont(size=12),
            text_color=DASHBOARD_THEME.text_secondary,
            anchor="w",
        ).grid(row=1, column=0, sticky="w", pady=(4, 0))

        selector_wrap = ctk.CTkFrame(header, fg_color="#16243b", corner_radius=16)
        selector_wrap.grid(row=1, column=1, sticky="ew", padx=(0, 16), pady=(0, 16))
        selector_wrap.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            selector_wrap,
            text="Displayed campaign",
            text_color=DASHBOARD_THEME.text_secondary,
            font=ctk.CTkFont(size=12, weight="bold"),
        ).grid(row=0, column=0, sticky="w", padx=12, pady=(10, 2))

        values = self._campaign_options or ["No campaigns"]
        self.campaign_var = tk.StringVar(value=values[0])
        self.campaign_selector = ctk.CTkOptionMenu(
            selector_wrap,
            variable=self.campaign_var,
            values=values,
            command=self._on_campaign_selected,
            fg_color=DASHBOARD_THEME.input_bg,
            button_color=DASHBOARD_THEME.input_button,
            button_hover_color=DASHBOARD_THEME.input_hover,
            text_color=DASHBOARD_THEME.text_primary,
            dropdown_fg_color=DASHBOARD_THEME.card_bg,
            dropdown_hover_color=DASHBOARD_THEME.button_hover,
            dropdown_text_color=DASHBOARD_THEME.text_primary,
        )
        self.campaign_selector.grid(row=1, column=0, columnspan=2, sticky="ew", padx=12, pady=(0, 12))

    def _build_body(self) -> None:
        self.scroll = ctk.CTkScrollableFrame(self, fg_color=DASHBOARD_THEME.panel_bg)
        self.scroll.grid(row=1, column=0, sticky="nsew", padx=16, pady=(0, 16))
        self.scroll.grid_columnconfigure(0, weight=1)

    def _load_initial_campaign(self) -> None:
        if self._campaign_options:
            self._on_campaign_selected(self._campaign_options[0])
        else:
            self._render_empty_state("No campaigns found in the active database.")

    def _safe_load(self, wrapper):
        try:
            return wrapper.load_items()
        except Exception:
            return []

    def _on_campaign_selected(self, selected_name: str) -> None:
        campaign = self._campaign_index.get(selected_name)
        self._selected_campaign = build_campaign_graph_payload(campaign, self._scenario_items)
        self._render_campaign()

    def _render_campaign(self) -> None:
        for child in self.scroll.winfo_children():
            child.destroy()

        payload = self._selected_campaign
        if payload is None:
            self._render_empty_state("Select a campaign to visualize its structure.")
            return

        self._render_campaign_hero(payload)
        if not payload.arcs:
            self._render_empty_state("This campaign does not contain any arc data yet.")
            return

        for row, arc in enumerate(payload.arcs, start=1):
            self._render_arc_card(arc, row)

    def _render_campaign_hero(self, payload: CampaignGraphPayload) -> None:
        hero = ctk.CTkFrame(self.scroll, fg_color="#10192b", corner_radius=24, border_width=1, border_color="#223554")
        hero.grid(row=0, column=0, sticky="ew", padx=8, pady=(0, 14))
        hero.grid_columnconfigure(1, weight=1)

        metrics = ctk.CTkFrame(hero, fg_color="#120f28", corner_radius=20, width=140)
        metrics.grid(row=0, column=0, sticky="ns", padx=(16, 10), pady=16)
        metrics.grid_propagate(False)
        ArcMomentumMeter(
            metrics,
            completed_steps=sum(1 for arc in payload.arcs if arc.status == "Completed"),
            total_steps=max(len(payload.arcs), 1),
            label="Arc completion",
        ).pack(padx=10, pady=(12, 10))
        ctk.CTkLabel(
            metrics,
            text=f"{payload.linked_scenario_count} linked scenarios",
            wraplength=110,
            justify="center",
            text_color=DASHBOARD_THEME.text_secondary,
        ).pack(padx=8, pady=(0, 12))

        details = ctk.CTkFrame(hero, fg_color="transparent")
        details.grid(row=0, column=1, sticky="ew", padx=(0, 16), pady=16)
        details.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            details,
            text=payload.name,
            font=ctk.CTkFont(size=28, weight="bold"),
            text_color=DASHBOARD_THEME.text_primary,
            anchor="w",
        ).grid(row=0, column=0, sticky="ew")

        chips = ctk.CTkFrame(details, fg_color="transparent")
        chips.grid(row=1, column=0, sticky="w", pady=(8, 10))
        for idx, value in enumerate([payload.genre, payload.tone, payload.status]):
            if not value:
                continue
            ctk.CTkLabel(
                chips,
                text=value,
                fg_color="#1b3150",
                corner_radius=999,
                padx=12,
                pady=4,
                text_color="#d8ebff",
                font=ctk.CTkFont(size=11, weight="bold"),
            ).grid(row=0, column=idx, padx=(0, 8))

        self._render_text_line(details, 2, "Logline", payload.logline)
        self._render_text_line(details, 3, "Setting", payload.setting)
        self._render_text_line(details, 4, "Main objective", payload.main_objective)
        self._render_text_line(details, 5, "Stakes", payload.stakes)
        self._render_text_line(details, 6, "Themes", payload.themes)

    def _render_text_line(self, parent, row: int, label: str, value: str) -> None:
        if not value:
            return
        block = ctk.CTkFrame(parent, fg_color="#162239", corner_radius=14)
        block.grid(row=row, column=0, sticky="ew", pady=4)
        block.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            block,
            text=label.upper(),
            text_color="#8fb0dd",
            font=ctk.CTkFont(size=10, weight="bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="w", padx=12, pady=(8, 2))
        ctk.CTkLabel(
            block,
            text=value,
            wraplength=760,
            justify="left",
            text_color=DASHBOARD_THEME.text_primary,
            anchor="w",
        ).grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 10))

    def _render_arc_card(self, arc: CampaignGraphArc, row: int) -> None:
        card = ctk.CTkFrame(self.scroll, fg_color=DASHBOARD_THEME.card_bg, corner_radius=22, border_width=1, border_color="#2b4161")
        card.grid(row=row, column=0, sticky="ew", padx=8, pady=10)
        card.grid_columnconfigure(1, weight=1)

        ArcMomentumMeter(
            card,
            completed_steps=len(arc.scenarios) if arc.status == "Completed" else max(1, len(arc.scenarios) // 2) if arc.status == "In Progress" else 0,
            total_steps=max(len(arc.scenarios), 1),
            label="Scenario pulse",
        ).grid(row=0, column=0, rowspan=3, sticky="ns", padx=(12, 6), pady=14)

        header = ctk.CTkFrame(card, fg_color="transparent")
        header.grid(row=0, column=1, sticky="ew", padx=(4, 14), pady=(14, 8))
        header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            header,
            text=arc.name,
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color=DASHBOARD_THEME.text_primary,
            anchor="w",
        ).grid(row=0, column=0, sticky="w")

        ctk.CTkLabel(
            header,
            text=arc.status,
            fg_color="#1f4c7d" if arc.status == "Planned" else "#6d28d9" if arc.status == "In Progress" else "#15803d",
            corner_radius=999,
            padx=12,
            pady=5,
            text_color="#f8fbff",
            font=ctk.CTkFont(size=11, weight="bold"),
        ).grid(row=0, column=1, sticky="e")

        if arc.summary:
            ctk.CTkLabel(card, text=f"Summary: {arc.summary}", wraplength=900, justify="left", anchor="w", text_color=DASHBOARD_THEME.text_secondary).grid(
                row=1, column=1, sticky="ew", padx=(4, 14), pady=(0, 4)
            )
        if arc.objective:
            ctk.CTkLabel(card, text=f"Objective: {arc.objective}", wraplength=900, justify="left", anchor="w", text_color="#d7e6ff").grid(
                row=2, column=1, sticky="ew", padx=(4, 14), pady=(0, 10)
            )

        if arc.scenarios:
            strip = ArcScenarioStrip(card, scenarios=arc.scenarios, on_open_scenario=self._open_scenario)
            strip.grid(row=3, column=0, columnspan=2, sticky="ew", padx=14, pady=(0, 10))

            scenario_area = ctk.CTkFrame(card, fg_color="transparent")
            scenario_area.grid(row=4, column=0, columnspan=2, sticky="ew", padx=10, pady=(0, 10))
            for column in range(2):
                scenario_area.grid_columnconfigure(column, weight=1)

            for index, scenario in enumerate(arc.scenarios):
                self._render_scenario_card(scenario_area, scenario, index)
        else:
            ctk.CTkLabel(
                card,
                text="No scenarios are currently attached to this arc.",
                text_color=DASHBOARD_THEME.text_secondary,
            ).grid(row=3, column=0, columnspan=2, sticky="ew", padx=14, pady=(0, 14))

    def _render_scenario_card(self, parent, scenario, index: int) -> None:
        card = ctk.CTkFrame(parent, fg_color="#0d1728", corner_radius=18, border_width=1, border_color="#22395d")
        card.grid(row=index // 2, column=index % 2, sticky="nsew", padx=6, pady=6)
        card.grid_columnconfigure(0, weight=1)

        header = ctk.CTkFrame(card, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 6))
        header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(header, text=scenario.title, font=ctk.CTkFont(size=16, weight="bold"), text_color=DASHBOARD_THEME.text_primary, anchor="w").grid(row=0, column=0, sticky="w")
        ctk.CTkButton(
            header,
            text="Edit scenario",
            width=110,
            fg_color=DASHBOARD_THEME.accent,
            hover_color=DASHBOARD_THEME.accent_hover,
            command=lambda n=scenario.title: self._open_scenario(n),
        ).grid(row=0, column=1, sticky="e")

        ctk.CTkLabel(
            card,
            text=scenario.summary or "No synopsis written yet for this scenario.",
            wraplength=460,
            justify="left",
            text_color=DASHBOARD_THEME.text_secondary,
            anchor="w",
        ).grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 10))

        constellation = EntityConstellation(card, links=scenario.entity_links, on_open_entity=self._open_entity)
        constellation.grid(row=2, column=0, sticky="ew", padx=12, pady=(0, 10))

        CapsuleWrap(card, items=scenario.entity_links, on_open_entity=self._open_entity).grid(row=3, column=0, sticky="ew", padx=8, pady=(0, 12))

    def _open_scenario(self, scenario_name: str) -> None:
        self._open_entity("Scenarios", scenario_name)

    def _open_entity(self, entity_type: str, entity_name: str) -> None:
        try:
            open_entity_tab(entity_type, entity_name, self.winfo_toplevel())
        except Exception as exc:
            messagebox.showerror("Open entity", f"Unable to open {entity_type} '{entity_name}':\n{exc}", parent=self.winfo_toplevel())

    def _render_empty_state(self, message: str) -> None:
        ctk.CTkLabel(
            self.scroll,
            text=message,
            text_color=DASHBOARD_THEME.text_secondary,
            font=ctk.CTkFont(size=14),
        ).grid(row=0, column=0, sticky="ew", padx=12, pady=24)
