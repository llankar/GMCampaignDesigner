from __future__ import annotations

import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox

from modules.generic.entity_detail_factory import open_entity_tab
from modules.generic.generic_model_wrapper import GenericModelWrapper
from modules.scenarios.gm_screen.dashboard.styles.dashboard_theme import DASHBOARD_THEME
from modules.scenarios.gm_screen.dashboard.widgets.arc_display.arc_momentum_meter import ArcMomentumMeter

from .components import ArcSelectorStrip, ScenarioSelectorStrip, ScenarioSpotlight
from .data import CampaignGraphArc, CampaignGraphPayload, build_campaign_graph_payload, build_campaign_option_index


class CampaignGraphPanel(ctk.CTkFrame):
    """RPG-forward campaign visualizer with focused arc and scenario browsing."""

    def __init__(self, master, *, campaign_wrapper=None, scenario_wrapper=None):
        super().__init__(master, fg_color=DASHBOARD_THEME.panel_bg)
        self.campaign_wrapper = campaign_wrapper or GenericModelWrapper("campaigns")
        self.scenario_wrapper = scenario_wrapper or GenericModelWrapper("scenarios")

        self._campaign_items = self._safe_load(self.campaign_wrapper)
        self._scenario_items = self._safe_load(self.scenario_wrapper)
        self._campaign_options, self._campaign_index = build_campaign_option_index(self._campaign_items)
        self._selected_campaign: CampaignGraphPayload | None = None
        self._selected_arc_index = 0
        self._selected_scenario_index = 0

        self._hero_mount = None
        self._content_mount = None
        self._arc_mount = None
        self._scenario_mount = None

        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self._build_header()
        self._build_body()
        self._load_initial_campaign()

    def _build_header(self) -> None:
        header = ctk.CTkFrame(self, fg_color=DASHBOARD_THEME.panel_alt_bg, corner_radius=20)
        header.grid(row=0, column=0, sticky="ew", padx=16, pady=(16, 10))
        header.grid_columnconfigure(1, weight=1)
        header.grid_columnconfigure(2, weight=0)

        crest = ctk.CTkFrame(header, fg_color="#20123f", corner_radius=16, width=68, height=68)
        crest.grid(row=0, column=0, padx=(14, 10), pady=14)
        crest.grid_propagate(False)
        ctk.CTkLabel(crest, text="✦", font=ctk.CTkFont(size=28, weight="bold"), text_color="#f7d774").place(relx=0.5, rely=0.4, anchor="center")
        ctk.CTkLabel(crest, text="GM", font=ctk.CTkFont(size=11, weight="bold"), text_color="#f3e8ff").place(relx=0.5, rely=0.72, anchor="center")

        text_wrap = ctk.CTkFrame(header, fg_color="transparent")
        text_wrap.grid(row=0, column=1, sticky="ew", pady=14)
        text_wrap.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            text_wrap,
            text="Campaign Constellation",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color=DASHBOARD_THEME.text_primary,
            anchor="w",
        ).grid(row=0, column=0, sticky="w")

        ctk.CTkLabel(
            text_wrap,
            text="Focus on one arc and one scenario at a time — without reloading the whole window.",
            font=ctk.CTkFont(size=12),
            text_color=DASHBOARD_THEME.text_secondary,
            anchor="w",
        ).grid(row=1, column=0, sticky="w", pady=(4, 0))

        selector_wrap = ctk.CTkFrame(header, fg_color="#16243b", corner_radius=16)
        selector_wrap.grid(row=0, column=2, sticky="e", padx=(10, 14), pady=14)
        selector_wrap.grid_columnconfigure(0, weight=1)

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
            width=260,
            fg_color=DASHBOARD_THEME.input_bg,
            button_color=DASHBOARD_THEME.input_button,
            button_hover_color=DASHBOARD_THEME.input_hover,
            text_color=DASHBOARD_THEME.text_primary,
            dropdown_fg_color=DASHBOARD_THEME.card_bg,
            dropdown_hover_color=DASHBOARD_THEME.button_hover,
            dropdown_text_color=DASHBOARD_THEME.text_primary,
        )
        self.campaign_selector.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 12))

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
        self._selected_arc_index = 0
        self._selected_scenario_index = 0
        self._render_campaign()

    def _render_campaign(self) -> None:
        self._clear_container(self.scroll)

        payload = self._selected_campaign
        if payload is None:
            self._render_empty_state("Select a campaign to visualize its structure.")
            return

        self._selected_arc_index = self._clamp_index(self._selected_arc_index, len(payload.arcs))
        selected_arc = self._get_selected_arc(payload)
        self._selected_scenario_index = self._clamp_index(
            self._selected_scenario_index,
            len(selected_arc.scenarios) if selected_arc is not None else 0,
        )

        self._hero_mount = ctk.CTkFrame(self.scroll, fg_color="transparent")
        self._hero_mount.grid(row=0, column=0, sticky="ew", padx=8, pady=(0, 12))
        self._content_mount = ctk.CTkFrame(self.scroll, fg_color="transparent")
        self._content_mount.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 12))
        self._content_mount.grid_columnconfigure(0, weight=1)

        self._render_campaign_hero(payload)
        self._refresh_arc_zone()

    def _render_campaign_hero(self, payload: CampaignGraphPayload) -> None:
        parent = self._hero_mount
        if parent is None:
            return

        hero = ctk.CTkFrame(parent, fg_color="#10192b", corner_radius=22, border_width=1, border_color="#223554")
        hero.grid(row=0, column=0, sticky="ew")
        for column in range(3):
            hero.grid_columnconfigure(column, weight=1 if column == 0 else 0)

        identity = ctk.CTkFrame(hero, fg_color="transparent")
        identity.grid(row=0, column=0, sticky="nsew", padx=(16, 10), pady=14)
        identity.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            identity,
            text=payload.name,
            font=ctk.CTkFont(size=26, weight="bold"),
            text_color=DASHBOARD_THEME.text_primary,
            anchor="w",
        ).grid(row=0, column=0, sticky="ew")

        chips = ctk.CTkFrame(identity, fg_color="transparent")
        chips.grid(row=1, column=0, sticky="w", pady=(8, 8))
        chip_column = 0
        for value in [payload.genre, payload.tone, payload.status]:
            if not value:
                continue
            ctk.CTkLabel(
                chips,
                text=value,
                fg_color="#1b3150",
                corner_radius=999,
                padx=10,
                pady=3,
                text_color="#d8ebff",
                font=ctk.CTkFont(size=11, weight="bold"),
            ).grid(row=0, column=chip_column, padx=(0, 8))
            chip_column += 1

        summary_text = payload.logline or payload.setting or payload.main_objective or "No campaign overview written yet."
        ctk.CTkLabel(
            identity,
            text=summary_text,
            wraplength=560,
            justify="left",
            text_color=DASHBOARD_THEME.text_secondary,
            anchor="w",
        ).grid(row=2, column=0, sticky="ew")

        metrics = ctk.CTkFrame(hero, fg_color="#120f28", corner_radius=18)
        metrics.grid(row=0, column=1, sticky="ns", padx=10, pady=14)
        ArcMomentumMeter(
            metrics,
            completed_steps=sum(1 for arc in payload.arcs if arc.status.lower() == "completed"),
            total_steps=max(len(payload.arcs), 1),
            label="Arc completion",
        ).pack(padx=12, pady=(12, 8))
        ctk.CTkLabel(
            metrics,
            text=f"{payload.linked_scenario_count} linked scenarios",
            wraplength=120,
            justify="center",
            text_color=DASHBOARD_THEME.text_secondary,
        ).pack(padx=8, pady=(0, 12))

        facts = ctk.CTkFrame(hero, fg_color="transparent")
        facts.grid(row=0, column=2, sticky="nsew", padx=(0, 16), pady=14)
        facts.grid_columnconfigure(0, weight=1)
        self._render_fact_tile(facts, 0, "Setting", payload.setting)
        self._render_fact_tile(facts, 1, "Objective", payload.main_objective)
        self._render_fact_tile(facts, 2, "Stakes", payload.stakes)
        self._render_fact_tile(facts, 3, "Themes", payload.themes)

    def _render_fact_tile(self, parent, row: int, label: str, value: str) -> None:
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
        ).grid(row=0, column=0, sticky="w", padx=12, pady=(7, 1))
        ctk.CTkLabel(
            block,
            text=value,
            wraplength=300,
            justify="left",
            text_color=DASHBOARD_THEME.text_primary,
            anchor="w",
        ).grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 8))

    def _refresh_arc_zone(self) -> None:
        parent = self._content_mount
        if parent is None:
            return
        self._clear_container(parent)

        payload = self._selected_campaign
        if payload is None:
            self._render_empty_state("Select a campaign to visualize its structure.", parent=parent)
            return
        if not payload.arcs:
            self._render_empty_state("This campaign does not contain any arc data yet.", parent=parent)
            return

        self._selected_arc_index = self._clamp_index(self._selected_arc_index, len(payload.arcs))
        selected_arc = payload.arcs[self._selected_arc_index]

        card = ctk.CTkFrame(parent, fg_color=DASHBOARD_THEME.card_bg, corner_radius=22, border_width=1, border_color="#2b4161")
        card.grid(row=0, column=0, sticky="nsew")
        card.grid_columnconfigure(0, weight=1)
        card.grid_rowconfigure(3, weight=1)
        self._arc_mount = card

        header = ctk.CTkFrame(card, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=14, pady=(14, 8))
        header.grid_columnconfigure(1, weight=1)

        self._render_stepper_controls(
            header,
            row=0,
            title="Current arc",
            subtitle=f"Arc {self._selected_arc_index + 1} of {len(payload.arcs)}",
            current_label=selected_arc.name,
            status_label=selected_arc.status,
            prev_command=lambda: self._shift_arc(-1),
            next_command=lambda: self._shift_arc(1),
            prev_enabled=self._selected_arc_index > 0,
            next_enabled=self._selected_arc_index < len(payload.arcs) - 1,
        )

        ArcSelectorStrip(
            card,
            arcs=payload.arcs,
            selected_index=self._selected_arc_index,
            on_select=self._select_arc,
        ).grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 12))

        summary_grid = ctk.CTkFrame(card, fg_color="transparent")
        summary_grid.grid(row=2, column=0, sticky="ew", padx=14, pady=(0, 12))
        for column in range(2):
            summary_grid.grid_columnconfigure(column, weight=1)

        self._render_focus_tile(
            summary_grid,
            column=0,
            title="Arc summary",
            body=selected_arc.summary or "No summary written yet for this arc.",
            accent="#7dd3fc",
        )
        self._render_focus_tile(
            summary_grid,
            column=1,
            title="Arc objective",
            body=selected_arc.objective or "No objective defined yet for this arc.",
            accent="#c084fc",
        )

        self._scenario_mount = ctk.CTkFrame(card, fg_color="transparent")
        self._scenario_mount.grid(row=3, column=0, sticky="nsew", padx=14, pady=(0, 14))
        self._scenario_mount.grid_columnconfigure(0, weight=1)
        self._scenario_mount.grid_rowconfigure(0, weight=1)
        self._refresh_scenario_zone()

    def _render_stepper_controls(
        self,
        parent,
        *,
        row: int,
        title: str,
        subtitle: str,
        current_label: str,
        status_label: str,
        prev_command,
        next_command,
        prev_enabled: bool,
        next_enabled: bool,
    ) -> None:
        label_wrap = ctk.CTkFrame(parent, fg_color="transparent")
        label_wrap.grid(row=row, column=0, columnspan=2, sticky="w")
        ctk.CTkLabel(
            label_wrap,
            text=title.upper(),
            text_color="#8fb0dd",
            font=ctk.CTkFont(size=10, weight="bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(
            label_wrap,
            text=subtitle,
            text_color=DASHBOARD_THEME.text_secondary,
            font=ctk.CTkFont(size=12),
            anchor="w",
        ).grid(row=1, column=0, sticky="w", pady=(2, 0))

        ctk.CTkLabel(
            parent,
            text=current_label,
            font=ctk.CTkFont(size=24, weight="bold"),
            text_color=DASHBOARD_THEME.text_primary,
            anchor="w",
        ).grid(row=row + 1, column=0, sticky="w")

        ctk.CTkLabel(
            parent,
            text=status_label,
            fg_color=self._status_color(status_label),
            corner_radius=999,
            padx=12,
            pady=5,
            text_color="#f8fbff",
            font=ctk.CTkFont(size=11, weight="bold"),
        ).grid(row=row + 1, column=1, sticky="e", padx=(8, 0))

        controls = ctk.CTkFrame(parent, fg_color="transparent")
        controls.grid(row=row, column=2, rowspan=2, sticky="e")
        ctk.CTkButton(
            controls,
            text="← Previous",
            width=104,
            command=prev_command,
            state="normal" if prev_enabled else "disabled",
            fg_color="#17263d",
            hover_color="#223a5f",
            text_color="#f2f6ff",
        ).grid(row=0, column=0, padx=(0, 8))
        ctk.CTkButton(
            controls,
            text="Next →",
            width=104,
            command=next_command,
            state="normal" if next_enabled else "disabled",
            fg_color=DASHBOARD_THEME.accent,
            hover_color=DASHBOARD_THEME.accent_hover,
            text_color="#f8fbff",
        ).grid(row=0, column=1)

    def _render_focus_tile(self, parent, *, column: int, title: str, body: str, accent: str) -> None:
        tile = ctk.CTkFrame(parent, fg_color="#0d1728", corner_radius=18, border_width=1, border_color="#22395d")
        tile.grid(row=0, column=column, sticky="nsew", padx=6)
        tile.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            tile,
            text=title.upper(),
            text_color=accent,
            font=ctk.CTkFont(size=10, weight="bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="w", padx=14, pady=(12, 6))
        ctk.CTkLabel(
            tile,
            text=body,
            wraplength=460,
            justify="left",
            text_color=DASHBOARD_THEME.text_primary,
            anchor="w",
        ).grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 14))

    def _refresh_scenario_zone(self) -> None:
        parent = self._scenario_mount
        if parent is None:
            return
        self._clear_container(parent)

        payload = self._selected_campaign
        selected_arc = self._get_selected_arc(payload) if payload is not None else None
        if selected_arc is None:
            self._render_empty_state("Select an arc to inspect its scenarios.", parent=parent)
            return

        section = ctk.CTkFrame(parent, fg_color="#111a2c", corner_radius=20)
        section.grid(row=0, column=0, sticky="nsew")
        section.grid_columnconfigure(0, weight=1)
        section.grid_rowconfigure(2, weight=1)

        if not selected_arc.scenarios:
            ctk.CTkLabel(
                section,
                text="No scenarios are currently attached to this arc.",
                text_color=DASHBOARD_THEME.text_secondary,
                font=ctk.CTkFont(size=14),
            ).grid(row=0, column=0, sticky="ew", padx=14, pady=18)
            return

        self._selected_scenario_index = self._clamp_index(self._selected_scenario_index, len(selected_arc.scenarios))
        selected_scenario = selected_arc.scenarios[self._selected_scenario_index]

        header = ctk.CTkFrame(section, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=14, pady=(14, 8))
        header.grid_columnconfigure(1, weight=1)
        self._render_stepper_controls(
            header,
            row=0,
            title="Current scenario",
            subtitle=f"Scenario {self._selected_scenario_index + 1} of {len(selected_arc.scenarios)}",
            current_label=selected_scenario.title,
            status_label=f"{len(selected_scenario.entity_links)} links",
            prev_command=lambda: self._shift_scenario(-1),
            next_command=lambda: self._shift_scenario(1),
            prev_enabled=self._selected_scenario_index > 0,
            next_enabled=self._selected_scenario_index < len(selected_arc.scenarios) - 1,
        )

        ScenarioSelectorStrip(
            section,
            scenarios=selected_arc.scenarios,
            selected_index=self._selected_scenario_index,
            on_select=self._select_scenario,
        ).grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 12))

        ScenarioSpotlight(
            section,
            scenario=selected_scenario,
            on_open_scenario=self._open_scenario,
            on_open_entity=self._open_entity,
        ).grid(row=2, column=0, sticky="nsew", padx=14, pady=(0, 14))

    def _get_selected_arc(self, payload: CampaignGraphPayload | None) -> CampaignGraphArc | None:
        if payload is None or not payload.arcs:
            return None
        return payload.arcs[self._clamp_index(self._selected_arc_index, len(payload.arcs))]

    def _shift_arc(self, step: int) -> None:
        payload = self._selected_campaign
        if payload is None or not payload.arcs:
            return
        self._selected_arc_index = self._clamp_index(self._selected_arc_index + step, len(payload.arcs))
        self._selected_scenario_index = 0
        self._refresh_arc_zone()

    def _shift_scenario(self, step: int) -> None:
        payload = self._selected_campaign
        selected_arc = self._get_selected_arc(payload)
        if selected_arc is None or not selected_arc.scenarios:
            return
        self._selected_scenario_index = self._clamp_index(self._selected_scenario_index + step, len(selected_arc.scenarios))
        self._refresh_scenario_zone()

    def _select_arc(self, index: int) -> None:
        payload = self._selected_campaign
        if payload is None or not payload.arcs:
            return
        self._selected_arc_index = self._clamp_index(index, len(payload.arcs))
        self._selected_scenario_index = 0
        self._refresh_arc_zone()

    def _select_scenario(self, index: int) -> None:
        payload = self._selected_campaign
        selected_arc = self._get_selected_arc(payload)
        if selected_arc is None or not selected_arc.scenarios:
            return
        self._selected_scenario_index = self._clamp_index(index, len(selected_arc.scenarios))
        self._refresh_scenario_zone()

    def _status_color(self, status_label: str) -> str:
        status = status_label.lower()
        if "completed" in status:
            return "#15803d"
        if "progress" in status or "link" in status:
            return "#6d28d9"
        return "#1f4c7d"

    def _clamp_index(self, index: int, length: int) -> int:
        if length <= 0:
            return 0
        return max(0, min(index, length - 1))

    def _clear_container(self, parent) -> None:
        for child in parent.winfo_children():
            child.destroy()

    def _open_scenario(self, scenario_name: str) -> None:
        self._open_entity("Scenarios", scenario_name)

    def _open_entity(self, entity_type: str, entity_name: str) -> None:
        try:
            open_entity_tab(entity_type, entity_name, self.winfo_toplevel())
        except Exception as exc:
            messagebox.showerror("Open entity", f"Unable to open {entity_type} '{entity_name}':\n{exc}", parent=self.winfo_toplevel())

    def _render_empty_state(self, message: str, *, parent=None) -> None:
        target = parent or self.scroll
        ctk.CTkLabel(
            target,
            text=message,
            text_color=DASHBOARD_THEME.text_secondary,
            font=ctk.CTkFont(size=14),
        ).grid(row=0, column=0, sticky="ew", padx=12, pady=24)
