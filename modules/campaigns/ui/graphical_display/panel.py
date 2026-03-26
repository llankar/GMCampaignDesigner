from __future__ import annotations

import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox

from modules.generic.entity_detail_factory import open_entity_tab
from modules.generic.generic_model_wrapper import GenericModelWrapper
from modules.scenarios.gm_screen.dashboard.styles.dashboard_theme import DASHBOARD_THEME
from .components import (
    CampaignOverviewHero,
    ArcSelectorStrip,
    ScenarioBriefingPanel,
    ScenarioEntityBrowser,
    ScenarioHeroStrip,
    ScenarioIdentityPanel,
    ScenarioSelectorStrip,
)
from .data import CampaignGraphArc, CampaignGraphPayload, CampaignGraphScenario, build_campaign_graph_payload, build_campaign_option_index
from modules.scenarios.gm_screen_view import GMScreenView
from modules.scenarios.gm_layout_manager import GMScreenLayoutManager
from .services import CampaignOverviewSelectionStore, open_scenario_in_embedded_gm_screen


class CampaignGraphPanel(ctk.CTkFrame):
    """RPG-forward campaign visualizer with focused arc and scenario browsing."""

    def __init__(self, master, *, campaign_wrapper=None, scenario_wrapper=None):
        super().__init__(master, fg_color=DASHBOARD_THEME.panel_bg)
        self.campaign_wrapper = campaign_wrapper or GenericModelWrapper("campaigns")
        self.scenario_wrapper = scenario_wrapper or GenericModelWrapper("scenarios")

        self._campaign_items = self._safe_load(self.campaign_wrapper)
        self._scenario_items = self._safe_load(self.scenario_wrapper)
        self._campaign_options, self._campaign_index = build_campaign_option_index(self._campaign_items)
        self._selection_store = CampaignOverviewSelectionStore()
        self._selected_campaign: CampaignGraphPayload | None = None
        self._selected_arc_index = 0
        self._selected_scenario_index = 0
        self._scenario_focus_container = None

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
            text="Campaign overview",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color=DASHBOARD_THEME.text_primary,
            anchor="w",
        ).grid(row=0, column=0, sticky="w")

        ctk.CTkLabel(
            text_wrap,
            text="Focus on one arc and one scenario at a time.",
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

        self._empty_state_label = ctk.CTkLabel(
            self.scroll,
            text="",
            text_color=DASHBOARD_THEME.text_secondary,
            font=ctk.CTkFont(size=14),
        )

        self._hero_container = ctk.CTkFrame(self.scroll, fg_color="transparent")
        self._hero_container.grid(row=0, column=0, sticky="ew")
        self._hero_container.grid_columnconfigure(0, weight=1)

        self._arc_focus_container = ctk.CTkFrame(self.scroll, fg_color="transparent")
        self._arc_focus_container.grid(row=1, column=0, sticky="nsew")
        self._arc_focus_container.grid_columnconfigure(0, weight=1)

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
        self._apply_saved_focus_state(campaign)
        self._scroll_to_top()
        self._refresh_campaign_content()

    def _apply_saved_focus_state(self, campaign_record: dict | None) -> None:
        payload = self._selected_campaign
        if payload is None or not payload.arcs:
            return

        saved_state = self._selection_store.load(campaign_record)
        if saved_state.arc_name:
            matching_arc_index = next(
                (index for index, arc in enumerate(payload.arcs) if arc.name == saved_state.arc_name),
                0,
            )
            self._selected_arc_index = self._clamp_index(matching_arc_index, len(payload.arcs))

        selected_arc = self._get_selected_arc(payload)
        if selected_arc is None or not selected_arc.scenarios:
            self._selected_scenario_index = 0
            return

        if saved_state.scenario_title:
            matching_scenario_index = next(
                (
                    index
                    for index, scenario in enumerate(selected_arc.scenarios)
                    if scenario.title == saved_state.scenario_title
                ),
                0,
            )
            self._selected_scenario_index = self._clamp_index(matching_scenario_index, len(selected_arc.scenarios))

    def _persist_focus_state(self) -> None:
        payload = self._selected_campaign
        if payload is None:
            return

        campaign_record = self._campaign_index.get(payload.name)
        selected_arc = self._get_selected_arc(payload)
        selected_scenario_title = ""
        if selected_arc and selected_arc.scenarios:
            selected_scenario = selected_arc.scenarios[self._selected_scenario_index]
            selected_scenario_title = selected_scenario.title

        updated_record = self._selection_store.save(
            campaign_record,
            arc_name=selected_arc.name if selected_arc else "",
            scenario_title=selected_scenario_title,
        )
        if isinstance(updated_record, dict):
            self._campaign_index[payload.name] = updated_record

    def _refresh_campaign_content(self) -> None:
        payload = self._selected_campaign
        if payload is None:
            self._clear_container(self._hero_container)
            self._clear_container(self._arc_focus_container)
            self._scenario_focus_container = None
            self._render_empty_state("Select a campaign to visualize its structure.")
            return

        self._hide_empty_state()
        self._refresh_campaign_hero()
        if not payload.arcs:
            self._clear_container(self._arc_focus_container)
            self._scenario_focus_container = None
            self._render_empty_state("This campaign does not contain any arc data yet.")
            return

        self._refresh_arc_focus()

    def _refresh_campaign_hero(self) -> None:
        payload = self._selected_campaign
        self._clear_container(self._hero_container)
        if payload is None:
            return
        self._render_campaign_hero(payload)

    def _refresh_arc_focus(self) -> None:
        def _refresh() -> None:
            payload = self._selected_campaign
            self._clear_container(self._arc_focus_container)
            self._scenario_focus_container = None
            if payload is None or not payload.arcs:
                return

            self._hide_empty_state()
            self._selected_arc_index = self._clamp_index(self._selected_arc_index, len(payload.arcs))
            selected_arc = self._get_selected_arc(payload)
            if selected_arc is None:
                return

            self._selected_scenario_index = self._clamp_index(self._selected_scenario_index, len(selected_arc.scenarios))
            self._render_arc_focus(payload, self._selected_arc_index)

        self._preserve_scroll_position(_refresh)

    def _refresh_scenario_focus(self) -> None:
        def _refresh() -> None:
            payload = self._selected_campaign
            selected_arc = self._get_selected_arc(payload) if payload is not None else None
            scenario_container = getattr(self, "_scenario_focus_container", None)
            if scenario_container is None:
                return

            self._clear_container(scenario_container)
            if selected_arc is None:
                return

            self._selected_scenario_index = self._clamp_index(self._selected_scenario_index, len(selected_arc.scenarios))
            self._render_scenario_focus(selected_arc)

        self._preserve_scroll_position(_refresh)

    def _render_campaign_hero(self, payload: CampaignGraphPayload) -> None:
        CampaignOverviewHero(self._hero_container, payload=payload).grid(
            row=0,
            column=0,
            sticky="ew",
            padx=8,
            pady=(0, 12),
        )

    def _render_arc_focus(self, payload: CampaignGraphPayload, selected_index: int) -> None:
        selected_arc = payload.arcs[selected_index]
        card = ctk.CTkFrame(self._arc_focus_container, fg_color=DASHBOARD_THEME.card_bg, corner_radius=22, border_width=1, border_color="#2b4161")
        card.grid(row=0, column=0, sticky="nsew", padx=8, pady=(0, 12))
        card.grid_columnconfigure(0, weight=1)
        card.grid_rowconfigure(3, weight=1)

        header = ctk.CTkFrame(card, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=14, pady=(14, 8))
        header.grid_columnconfigure(1, weight=1)

        self._render_stepper_controls(
            header,
            row=0,
            title="Current arc",
            subtitle=f"Arc {selected_index + 1} of {len(payload.arcs)}",
            current_label=selected_arc.name,
            status_label=selected_arc.status,
            prev_command=lambda: self._shift_arc(-1),
            next_command=lambda: self._shift_arc(1),
            prev_enabled=selected_index > 0,
            next_enabled=selected_index < len(payload.arcs) - 1,
        )

        ArcSelectorStrip(
            card,
            arcs=payload.arcs,
            selected_index=selected_index,
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

        self._scenario_focus_container = ctk.CTkFrame(card, fg_color="transparent")
        self._scenario_focus_container.grid(row=3, column=0, sticky="nsew")
        self._scenario_focus_container.grid_columnconfigure(0, weight=1)

        self._refresh_scenario_focus()

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

    def _render_scenario_focus(self, arc: CampaignGraphArc) -> None:
        section = ctk.CTkFrame(self._scenario_focus_container, fg_color="#111a2c", corner_radius=20)
        section.grid(row=0, column=0, sticky="nsew", padx=14, pady=(0, 14))
        section.grid_columnconfigure(0, weight=1)
        section.grid_rowconfigure(2, weight=1)

        if not arc.scenarios:
            ctk.CTkLabel(
                section,
                text="No scenarios are currently attached to this arc.",
                text_color=DASHBOARD_THEME.text_secondary,
                font=ctk.CTkFont(size=14),
            ).grid(row=0, column=0, sticky="ew", padx=14, pady=18)
            return

        selected_scenario = arc.scenarios[self._selected_scenario_index]

        header = ctk.CTkFrame(section, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=14, pady=(14, 8))
        header.grid_columnconfigure(1, weight=1)
        self._render_stepper_controls(
            header,
            row=0,
            title="Current scenario",
            subtitle=f"Scenario {self._selected_scenario_index + 1} of {len(arc.scenarios)}",
            current_label=selected_scenario.title,
            status_label=f"{len(selected_scenario.entity_links)} links",
            prev_command=lambda: self._shift_scenario(-1),
            next_command=lambda: self._shift_scenario(1),
            prev_enabled=self._selected_scenario_index > 0,
            next_enabled=self._selected_scenario_index < len(arc.scenarios) - 1,
        )

        ScenarioSelectorStrip(
            section,
            scenarios=arc.scenarios,
            selected_index=self._selected_scenario_index,
            on_select=self._select_scenario,
        ).grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 12))

        self._render_selected_scenario_card(section, arc, selected_scenario)

    def _render_selected_scenario_card(self, parent, arc: CampaignGraphArc, scenario: CampaignGraphScenario) -> None:
        card = ctk.CTkFrame(parent, fg_color="#0b1220", corner_radius=22, border_width=1, border_color="#22395d")
        card.grid(row=2, column=0, sticky="nsew", padx=14, pady=(0, 14))
        card.grid_columnconfigure(0, weight=1)
        card.grid_rowconfigure(1, weight=1)

        subtitle = f"{arc.name} • Scenario {self._selected_scenario_index + 1} of {len(arc.scenarios)}"
        gm_callback = (lambda n=scenario.title: self._open_scenario_gm_screen(n)) if scenario.record_exists else None

        ScenarioHeroStrip(
            card,
            title=scenario.title,
            subtitle=subtitle,
            count_chips=[
                ("linked entities", str(scenario.linked_entity_count)),
                ("places", str(scenario.linked_places_count)),
                ("factions", str(scenario.linked_factions_count)),
                ("villains", str(scenario.linked_villains_count)),
            ],
            on_edit=lambda n=scenario.title: self._open_scenario(n),
            on_open_gm_screen=gm_callback,
        ).grid(row=0, column=0, sticky="ew", padx=14, pady=(14, 10))

        content = ctk.CTkFrame(card, fg_color="transparent")
        content.grid(row=1, column=0, sticky="nsew", padx=14, pady=(0, 14))
        content.grid_columnconfigure(0, weight=3)
        content.grid_columnconfigure(1, weight=3)
        content.grid_rowconfigure(0, weight=0)
        content.grid_rowconfigure(1, weight=1)

        left_column = ctk.CTkFrame(content, fg_color="transparent")
        left_column.grid(row=0, column=0, rowspan=2, sticky="nsew", padx=(0, 12))
        left_column.grid_columnconfigure(0, weight=1)

        identity_summary = scenario.hook or scenario.summary or "No synopsis written yet for this scenario."
        ScenarioIdentityPanel(
            left_column,
            eyebrow="Mission profile",
            title=scenario.title,
            summary=identity_summary,
            tags=scenario.tags,
            progress_items=[
                ("linked entities", str(scenario.linked_entity_count)),
                ("primary cluster", scenario.primary_link_type or "Unassigned"),
                ("scenes", str(scenario.scene_count or 0)),
                ("status", "Secrets ready" if scenario.has_secrets else "Open notes"),
            ],
            on_edit=lambda n=scenario.title: self._open_scenario(n),
            on_open_gm_screen=gm_callback,
        ).grid(row=0, column=0, sticky="ew", pady=(0, 12))

        ScenarioBriefingPanel(
            left_column,
            summary=scenario.briefing or scenario.summary,
            objective=scenario.objective,
            hook=scenario.hook,
            stakes=scenario.stakes,
        ).grid(row=1, column=0, sticky="nsew")

        ScenarioEntityBrowser(
            content,
            scenario_title=scenario.title,
            links=scenario.entity_links,
            on_open_entity=self._open_entity,
        ).grid(row=0, column=1, rowspan=2, sticky="nsew")

    def _get_selected_arc(self, payload: CampaignGraphPayload) -> CampaignGraphArc | None:
        if not payload.arcs:
            return None
        return payload.arcs[self._clamp_index(self._selected_arc_index, len(payload.arcs))]

    def _shift_arc(self, step: int) -> None:
        payload = self._selected_campaign
        if payload is None or not payload.arcs:
            return
        self._selected_arc_index = self._clamp_index(self._selected_arc_index + step, len(payload.arcs))
        self._selected_scenario_index = 0
        self._persist_focus_state()
        self._refresh_arc_focus()

    def _shift_scenario(self, step: int) -> None:
        payload = self._selected_campaign
        selected_arc = self._get_selected_arc(payload) if payload is not None else None
        if selected_arc is None or not selected_arc.scenarios:
            return
        self._selected_scenario_index = self._clamp_index(self._selected_scenario_index + step, len(selected_arc.scenarios))
        self._persist_focus_state()
        self._refresh_scenario_focus()

    def _select_arc(self, index: int) -> None:
        payload = self._selected_campaign
        if payload is None or not payload.arcs:
            return
        self._selected_arc_index = self._clamp_index(index, len(payload.arcs))
        self._selected_scenario_index = 0
        self._persist_focus_state()
        self._refresh_arc_focus()

    def _select_scenario(self, index: int) -> None:
        payload = self._selected_campaign
        selected_arc = self._get_selected_arc(payload) if payload is not None else None
        if selected_arc is None or not selected_arc.scenarios:
            return
        self._selected_scenario_index = self._clamp_index(index, len(selected_arc.scenarios))
        self._persist_focus_state()
        self._refresh_scenario_focus()

    def _preserve_scroll_position(self, callback) -> None:
        scroll_fraction = self._get_scroll_fraction()
        callback()
        if scroll_fraction is not None:
            self.after_idle(lambda value=scroll_fraction: self._restore_scroll_fraction(value))

    def _get_scroll_fraction(self) -> float | None:
        canvas = self._get_scroll_canvas()
        if canvas is None or not hasattr(canvas, "yview"):
            return None
        try:
            return float(canvas.yview()[0])
        except Exception:
            return None

    def _restore_scroll_fraction(self, value: float) -> None:
        canvas = self._get_scroll_canvas()
        if canvas is None or not hasattr(canvas, "yview_moveto"):
            return
        try:
            canvas.update_idletasks()
            canvas.yview_moveto(value)
        except Exception:
            return

    def _scroll_to_top(self) -> None:
        self._restore_scroll_fraction(0.0)

    def _get_scroll_canvas(self):
        scroll = getattr(self, "scroll", None)
        if scroll is None:
            return None

        direct_canvas = getattr(scroll, "_parent_canvas", None)
        if direct_canvas is not None:
            return direct_canvas

        queue = [scroll]
        visited: set[int] = set()
        while queue:
            widget = queue.pop(0)
            widget_id = id(widget)
            if widget_id in visited:
                continue
            visited.add(widget_id)

            if isinstance(widget, tk.Canvas):
                return widget

            children_getter = getattr(widget, "winfo_children", None)
            if callable(children_getter):
                try:
                    queue.extend(children_getter())
                except Exception:
                    continue
        return None

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

    def _bind_wraplength(self, parent, label, *, horizontal_padding: int = 40, minimum: int = 240) -> None:
        def _update(_event=None):
            try:
                label.configure(wraplength=max(minimum, parent.winfo_width() - horizontal_padding))
            except Exception:
                pass

        parent.bind("<Configure>", _update, add="+")
        parent.after(50, _update)

    def _open_scenario(self, scenario_name: str) -> None:
        self._open_entity("Scenarios", scenario_name)

    def _open_scenario_gm_screen(self, scenario_name: str) -> None:
        scenario_item = next((item for item in self._scenario_items if str(item.get("Title") or "").strip() == scenario_name), None)
        if not isinstance(scenario_item, dict):
            messagebox.showerror("GM screen", f"Scenario '{scenario_name}' could not be loaded.", parent=self.winfo_toplevel())
            return

        def _fallback() -> None:
            try:
                window = ctk.CTkToplevel(self)
                window.title(f"Scenario: {scenario_name}")
                window.geometry("1920x1080+0+0")
                layout_manager = GMScreenLayoutManager()
                view = GMScreenView(window, scenario_item=scenario_item, initial_layout=None, layout_manager=layout_manager)
                view.pack(fill="both", expand=True)
            except Exception as exc:
                messagebox.showerror("GM screen", f"Unable to open the GM screen for '{scenario_name}':\n{exc}", parent=self.winfo_toplevel())

        open_scenario_in_embedded_gm_screen(self, scenario_name, fallback=_fallback)

    def _open_entity(self, entity_type: str, entity_name: str) -> None:
        try:
            open_entity_tab(entity_type, entity_name, self.winfo_toplevel())
        except Exception as exc:
            messagebox.showerror("Open entity", f"Unable to open {entity_type} '{entity_name}':\n{exc}", parent=self.winfo_toplevel())

    def _render_empty_state(self, message: str) -> None:
        self._empty_state_label.configure(text=message)
        self._empty_state_label.grid(row=0, column=0, sticky="ew", padx=12, pady=24)

    def _hide_empty_state(self) -> None:
        self._empty_state_label.grid_forget()

    def _clear_container(self, container) -> None:
        for child in container.winfo_children():
            child.destroy()
