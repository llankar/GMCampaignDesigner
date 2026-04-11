"""Panel for campaign."""

from __future__ import annotations

import customtkinter as ctk
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox

from modules.generic.entity_detail_factory import open_entity_tab
from modules.generic.generic_model_wrapper import GenericModelWrapper
from modules.scenarios.gm_screen.dashboard.styles.dashboard_theme import DASHBOARD_THEME
from modules.helpers import theme_manager
from modules.campaigns.services.poster_export import build_poster_theme_from_tokens, render_campaign_poster
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
from . import services as _graph_services


class CampaignOverviewSelectionStore(getattr(_graph_services, "CampaignOverviewSelectionStore", object)):
    """Selection store shim that stays compatible with lightweight test stubs."""

    def load(self, campaign_record):
        base = super()
        if hasattr(base, "load"):
            return base.load(campaign_record)
        return type("_State", (), {"arc_name": "", "scenario_title": ""})()

    def save(self, campaign_record, **kwargs):
        base = super()
        if hasattr(base, "save"):
            return base.save(campaign_record, **kwargs)
        return campaign_record


open_scenario_in_embedded_gm_screen = getattr(
    _graph_services,
    "open_scenario_in_embedded_gm_screen",
    lambda _widget, _scenario_name, fallback: fallback(),
)



class CampaignGraphPanel(ctk.CTkFrame):
    """RPG-forward campaign visualizer with focused arc and scenario browsing."""

    def __init__(self, master, *, campaign_wrapper=None, scenario_wrapper=None):
        """Initialize the CampaignGraphPanel instance."""
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
        self._scenario_section = None
        self._scenario_selector_strip = None
        self._scenario_left_column = None
        self._scenario_sidebar_container = None
        self._scenario_right_stack = None
        self._pending_sidebar_job = None
        self._pending_sidebar_target: tuple[str, str] | None = None

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        values = self._campaign_options or ["No campaigns"]
        self.campaign_var = tk.StringVar(value=values[0])

        self._build_body()
        self._load_initial_campaign()

    def _build_body(self) -> None:
        """Build body."""
        self.scroll = ctk.CTkScrollableFrame(self, fg_color=DASHBOARD_THEME.panel_bg)
        self.scroll.grid(row=0, column=0, sticky="nsew", padx=2, pady=2)
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
        """Load initial campaign."""
        if self._campaign_options:
            self._on_campaign_selected(self._campaign_options[0])
        else:
            self._render_empty_state("No campaigns found in the active database.")

    def _safe_load(self, wrapper):
        """Internal helper for safe load."""
        try:
            return wrapper.load_items()
        except Exception:
            return []

    def _on_campaign_selected(self, selected_name: str) -> None:
        """Handle campaign selected."""
        self._cancel_pending_sidebar_render()
        campaign = self._campaign_index.get(selected_name)
        self._selected_campaign = build_campaign_graph_payload(campaign, self._scenario_items)
        self._selected_arc_index = 0
        self._selected_scenario_index = 0
        self._apply_saved_focus_state(campaign)
        self._scroll_to_top()
        self._refresh_campaign_content()

    def _apply_saved_focus_state(self, campaign_record: dict | None) -> None:
        """Apply saved focus state."""
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
        """Persist focus state."""
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
        """Refresh campaign content."""
        self._cancel_pending_sidebar_render()
        payload = self._selected_campaign
        if payload is None:
            self._clear_container(self._hero_container)
            self._clear_container(self._arc_focus_container)
            self._scenario_focus_container = None
            self._scenario_section = None
            self._scenario_selector_strip = None
            self._scenario_left_column = None
            self._scenario_sidebar_container = None
            self._scenario_right_stack = None
            self._render_empty_state("Select a campaign to visualize its structure.")
            return

        self._hide_empty_state()
        self._refresh_campaign_hero()
        if not payload.arcs:
            self._clear_container(self._arc_focus_container)
            self._scenario_focus_container = None
            self._scenario_section = None
            self._scenario_selector_strip = None
            self._scenario_left_column = None
            self._scenario_sidebar_container = None
            self._scenario_right_stack = None
            self._render_empty_state("This campaign does not contain any arc data yet.")
            return

        self._refresh_arc_focus()

    def _refresh_campaign_hero(self) -> None:
        """Refresh campaign hero."""
        payload = self._selected_campaign
        self._clear_container(self._hero_container)
        if payload is None:
            return
        self._render_campaign_hero(payload)

    def _refresh_arc_focus(self) -> None:
        """Refresh arc focus."""
        self._cancel_pending_sidebar_render()
        def _refresh() -> None:
            """Refresh the operation."""
            payload = self._selected_campaign
            self._clear_container(self._arc_focus_container)
            self._scenario_focus_container = None
            self._scenario_section = None
            self._scenario_selector_strip = None
            self._scenario_left_column = None
            self._scenario_sidebar_container = None
            self._scenario_right_stack = None
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
        """Refresh scenario focus."""
        def _refresh() -> None:
            """Refresh the operation."""
            payload = self._selected_campaign
            selected_arc = self._get_selected_arc(payload) if payload is not None else None
            scenario_container = getattr(self, "_scenario_focus_container", None)
            if scenario_container is None:
                return

            if selected_arc is None:
                return

            self._selected_scenario_index = self._clamp_index(self._selected_scenario_index, len(selected_arc.scenarios))
            self._render_scenario_focus(selected_arc)

        self._preserve_scroll_position(_refresh)

    def _render_campaign_hero(self, payload: CampaignGraphPayload) -> None:
        """Render campaign hero."""
        CampaignOverviewHero(
            self._hero_container,
            payload=payload,
            campaign_var=self.campaign_var,
            campaign_values=self._campaign_options or ["No campaigns"],
            on_campaign_selected=self._on_campaign_selected,
            on_export_poster=self._export_campaign_poster,
        ).grid(
            row=0,
            column=0,
            sticky="ew",
            padx=2,
            pady=(0, 8),
        )

    def _export_campaign_poster(self) -> None:
        """Export the currently selected campaign as a static poster image."""
        payload = self._selected_campaign
        if payload is None:
            messagebox.showwarning("No campaign", "Select a campaign before exporting a poster.")
            return

        default_name = f"{payload.name.strip() or 'campaign'}_poster".replace(" ", "_")
        output_path = filedialog.asksaveasfilename(
            parent=self,
            title="Export campaign poster",
            defaultextension=".png",
            initialfile=f"{default_name}.png",
            filetypes=[("PNG image", "*.png")],
        )
        if not output_path:
            return

        tokens = theme_manager.get_tokens()
        theme = build_poster_theme_from_tokens(tokens)

        try:
            rendered_path = render_campaign_poster(payload, Path(output_path), theme=theme)
        except Exception as exc:
            messagebox.showerror("Export failed", f"Failed to render campaign poster:\n{exc}")
            return

        messagebox.showinfo("Poster exported", f"Campaign poster exported to:\n{rendered_path}")

    def _render_arc_focus(self, payload: CampaignGraphPayload, selected_index: int) -> None:
        """Render arc focus."""
        selected_arc = payload.arcs[selected_index]
        card = ctk.CTkFrame(self._arc_focus_container, fg_color=DASHBOARD_THEME.card_bg, corner_radius=22, border_width=1, border_color="#2b4161")
        card.grid(row=0, column=0, sticky="nsew", padx=2, pady=(0, 8))
        card.grid_columnconfigure(0, weight=1)
        card.grid_rowconfigure(3, weight=1)

        header = ctk.CTkFrame(card, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=14, pady=(10, 4))
        header.grid_columnconfigure(1, weight=1)

        self._render_stepper_controls(
            header,
            row=0,
            title="",
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
        """Render stepper controls."""
        label_wrap = ctk.CTkFrame(parent, fg_color="transparent")
        label_wrap.grid(row=row, column=0, columnspan=2, sticky="w")
        subtitle_row = 0
        if title:
            ctk.CTkLabel(
                label_wrap,
                text=title.upper(),
                text_color="#8fb0dd",
                font=ctk.CTkFont(size=9, weight="bold"),
                anchor="w",
            ).grid(row=0, column=0, sticky="w")
            subtitle_row = 1

        ctk.CTkLabel(
            label_wrap,
            text=subtitle,
            text_color=DASHBOARD_THEME.text_secondary,
            font=ctk.CTkFont(size=11),
            anchor="w",
        ).grid(row=subtitle_row, column=0, sticky="w", pady=(2, 0) if subtitle_row else 0)

        ctk.CTkLabel(
            parent,
            text=current_label,
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=DASHBOARD_THEME.text_primary,
            anchor="w",
            wraplength=760,
            justify="left",
        ).grid(row=row + 1, column=0, columnspan=2, sticky="w", padx=(0, 18))

        status_stack = ctk.CTkFrame(parent, fg_color="transparent")
        status_stack.grid(row=row, column=2, rowspan=2, sticky="ne", padx=(22, 0))

        ctk.CTkLabel(
            status_stack,
            text=status_label,
            fg_color=self._status_color(status_label),
            corner_radius=999,
            padx=12,
            pady=4,
            text_color=self._status_text_color(status_label),
            font=ctk.CTkFont(size=10, weight="bold"),
        ).pack(anchor="e", pady=(0, 8))

        controls = ctk.CTkFrame(status_stack, fg_color="transparent")
        controls.pack(anchor="e")
        ctk.CTkButton(
            controls,
            text="\u2190 Previous",
            width=96,
            height=30,
            command=prev_command,
            state="normal" if prev_enabled else "disabled",
            fg_color=DASHBOARD_THEME.button_fg,
            hover_color=DASHBOARD_THEME.button_hover,
            text_color=DASHBOARD_THEME.text_primary,
            font=ctk.CTkFont(size=11),
        ).grid(row=0, column=0, padx=(0, 8))
        ctk.CTkButton(
            controls,
            text="Next \u2192",
            width=96,
            height=30,
            command=next_command,
            state="normal" if next_enabled else "disabled",
            fg_color=DASHBOARD_THEME.accent,
            hover_color=DASHBOARD_THEME.accent_hover,
            text_color="#f8fbff",
            font=ctk.CTkFont(size=11),
        ).grid(row=0, column=1)

    def _render_focus_tile(self, parent, *, column: int, title: str, body: str, accent: str) -> None:
        """Render focus tile."""
        tile = ctk.CTkFrame(parent, fg_color=DASHBOARD_THEME.panel_alt_bg, corner_radius=18, border_width=1, border_color=DASHBOARD_THEME.card_border)
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
        """Render scenario focus."""
        self._render_or_update_scenario_focus(arc)
        return
        section = ctk.CTkFrame(self._scenario_focus_container, fg_color=DASHBOARD_THEME.panel_bg, corner_radius=20)
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
        header.grid(row=0, column=0, sticky="ew", padx=14, pady=(10, 4))
        header.grid_columnconfigure(1, weight=1)
        self._render_stepper_controls(
            header,
            row=0,
            title="",
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
        """Render selected scenario card."""
        card = ctk.CTkFrame(parent, fg_color=DASHBOARD_THEME.panel_alt_bg, corner_radius=22, border_width=1, border_color=DASHBOARD_THEME.card_border)
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

    def _render_or_update_scenario_focus(self, arc: CampaignGraphArc) -> None:
        """Render the scenario shell once, then update the active scenario in place."""
        container = getattr(self, "_scenario_focus_container", None)
        if container is None:
            return

        section = getattr(self, "_scenario_section", None)
        if section is None or not hasattr(section, "winfo_exists") or not section.winfo_exists():
            self._build_scenario_focus_shell(arc)
            return

        self._update_selected_scenario_focus(arc)

    def _build_scenario_focus_shell(self, arc: CampaignGraphArc) -> None:
        """Build the scenario shell for the active arc."""
        container = getattr(self, "_scenario_focus_container", None)
        if container is None:
            return

        self._cancel_pending_sidebar_render()
        self._clear_container(container)

        self._scenario_section = ctk.CTkFrame(container, fg_color=DASHBOARD_THEME.panel_bg, corner_radius=20)
        self._scenario_section.grid(row=0, column=0, sticky="nsew", padx=14, pady=(0, 14))
        self._scenario_section.grid_columnconfigure(0, weight=1)
        self._scenario_section.grid_rowconfigure(2, weight=1)
        self._scenario_right_stack = None

        if not arc.scenarios:
            self._scenario_selector_strip = None
            self._scenario_left_column = None
            self._scenario_sidebar_container = None
            ctk.CTkLabel(
                self._scenario_section,
                text="No scenarios are currently attached to this arc.",
                text_color=DASHBOARD_THEME.text_secondary,
                font=ctk.CTkFont(size=14),
            ).grid(row=0, column=0, sticky="ew", padx=14, pady=18)
            return

        header = ctk.CTkFrame(self._scenario_section, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=14, pady=(10, 4))
        header.grid_columnconfigure(1, weight=1)
        self._scenario_subtitle_label = ctk.CTkLabel(
            header,
            text="",
            text_color=DASHBOARD_THEME.text_secondary,
            font=ctk.CTkFont(size=11),
            anchor="w",
        )
        self._scenario_subtitle_label.grid(row=0, column=0, sticky="w")
        self._scenario_title_label = ctk.CTkLabel(
            header,
            text="",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=DASHBOARD_THEME.text_primary,
            anchor="w",
            wraplength=760,
            justify="left",
        )
        self._scenario_title_label.grid(row=1, column=0, columnspan=2, sticky="w", padx=(0, 18))
        right_stack = ctk.CTkFrame(header, fg_color="transparent")
        right_stack.grid(row=0, column=2, rowspan=2, sticky="ne", padx=(22, 0))
        self._scenario_right_stack = right_stack
        self._scenario_status_label = ctk.CTkLabel(
            right_stack,
            text="",
            fg_color=DASHBOARD_THEME.arc_planned,
            corner_radius=999,
            padx=12,
            pady=4,
            text_color="#f8fbff",
            font=ctk.CTkFont(size=10, weight="bold"),
        )
        self._scenario_status_label.pack(anchor="e", pady=(0, 8))

        controls = ctk.CTkFrame(right_stack, fg_color="transparent")
        controls.pack(anchor="e")
        self._scenario_prev_button = ctk.CTkButton(
            controls,
            text="\u2190 Previous",
            width=96,
            height=30,
            command=lambda: self._shift_scenario(-1),
            fg_color=DASHBOARD_THEME.button_fg,
            hover_color=DASHBOARD_THEME.button_hover,
            text_color=DASHBOARD_THEME.text_primary,
            font=ctk.CTkFont(size=11),
        )
        self._scenario_prev_button.grid(row=0, column=0, padx=(0, 8))
        self._scenario_next_button = ctk.CTkButton(
            controls,
            text="Next \u2192",
            width=96,
            height=30,
            command=lambda: self._shift_scenario(1),
            fg_color=DASHBOARD_THEME.accent,
            hover_color=DASHBOARD_THEME.accent_hover,
            text_color="#f8fbff",
            font=ctk.CTkFont(size=11),
        )
        self._scenario_next_button.grid(row=0, column=1)

        self._scenario_selector_strip = ScenarioSelectorStrip(
            self._scenario_section,
            scenarios=arc.scenarios,
            selected_index=self._selected_scenario_index,
            on_select=self._select_scenario,
        )
        self._scenario_selector_strip.grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 12))
        if hasattr(self._scenario_selector_strip, "set_scenarios"):
            self._scenario_selector_strip.set_scenarios(arc.scenarios, self._selected_scenario_index)

        self._scenario_card = ctk.CTkFrame(self._scenario_section, fg_color=DASHBOARD_THEME.panel_alt_bg, corner_radius=22, border_width=1, border_color=DASHBOARD_THEME.card_border)
        self._scenario_card.grid(row=2, column=0, sticky="nsew", padx=14, pady=(0, 14))
        self._scenario_card.grid_columnconfigure(0, weight=1)
        self._scenario_card.grid_rowconfigure(1, weight=1)

        self._scenario_primary = ctk.CTkFrame(self._scenario_card, fg_color="transparent")
        self._scenario_primary.grid(row=0, column=0, sticky="ew", padx=14, pady=(14, 10))
        self._scenario_primary.grid_columnconfigure(0, weight=1)

        self._scenario_content = ctk.CTkFrame(self._scenario_card, fg_color="transparent")
        self._scenario_content.grid(row=1, column=0, sticky="nsew", padx=14, pady=(0, 14))
        self._scenario_content.grid_columnconfigure(0, weight=3)
        self._scenario_content.grid_columnconfigure(1, weight=3)
        self._scenario_content.grid_rowconfigure(0, weight=1)

        self._scenario_left_column = ctk.CTkFrame(self._scenario_content, fg_color="transparent")
        self._scenario_left_column.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        self._scenario_left_column.grid_columnconfigure(0, weight=1)

        self._scenario_sidebar_container = ctk.CTkFrame(self._scenario_content, fg_color="transparent")
        self._scenario_sidebar_container.grid(row=0, column=1, sticky="nsew")
        self._scenario_sidebar_container.grid_columnconfigure(0, weight=1)

        self._update_selected_scenario_focus(arc)

    def _update_selected_scenario_focus(self, arc: CampaignGraphArc) -> None:
        """Refresh the selected scenario without rebuilding the shell."""
        if not arc.scenarios:
            return

        selected_index = self._clamp_index(self._selected_scenario_index, len(arc.scenarios))
        self._selected_scenario_index = selected_index
        selected_scenario = arc.scenarios[selected_index]

        selector = getattr(self, "_scenario_selector_strip", None)
        if selector is not None:
            if hasattr(selector, "set_selected_index"):
                selector.set_selected_index(selected_index)
            elif hasattr(selector, "set_scenarios"):
                selector.set_scenarios(arc.scenarios, selected_index)

        prev_button = getattr(self, "_scenario_prev_button", None)
        next_button = getattr(self, "_scenario_next_button", None)
        if prev_button is not None:
            prev_button.configure(state="normal" if selected_index > 0 else "disabled")
        if next_button is not None:
            next_button.configure(state="normal" if selected_index < len(arc.scenarios) - 1 else "disabled")

        subtitle_label = getattr(self, "_scenario_subtitle_label", None)
        title_label = getattr(self, "_scenario_title_label", None)
        status_label = getattr(self, "_scenario_status_label", None)
        if subtitle_label is not None:
            subtitle_label.configure(text=f"Scenario {selected_index + 1} of {len(arc.scenarios)}")
        if title_label is not None:
            title_label.configure(text=selected_scenario.title)
        if status_label is not None:
            status_label.configure(
                text=f"{len(selected_scenario.entity_links)} links",
                fg_color=self._status_color(f"{len(selected_scenario.entity_links)} links"),
            )

        self._render_selected_scenario_primary(arc, selected_scenario)
        self._render_scenario_sidebar_placeholder(selected_scenario, arc)
        self._schedule_scenario_sidebar_render(arc, selected_scenario)

    def _render_selected_scenario_primary(self, arc: CampaignGraphArc, scenario: CampaignGraphScenario) -> None:
        """Render the primary selected scenario content immediately."""
        primary = getattr(self, "_scenario_primary", None)
        left_column = getattr(self, "_scenario_left_column", None)
        if primary is None or left_column is None:
            return

        self._clear_container(primary)
        self._clear_container(left_column)

        gm_callback = (lambda n=scenario.title: self._open_scenario_gm_screen(n)) if scenario.record_exists else None
        ScenarioHeroStrip(
            primary,
            title=scenario.title,
            subtitle=f"{arc.name} • Scenario {self._selected_scenario_index + 1} of {len(arc.scenarios)}",
            count_chips=[
                ("linked entities", str(scenario.linked_entity_count)),
                ("places", str(scenario.linked_places_count)),
                ("factions", str(scenario.linked_factions_count)),
                ("villains", str(scenario.linked_villains_count)),
            ],
            on_edit=lambda n=scenario.title: self._open_scenario(n),
            on_open_gm_screen=gm_callback,
        ).grid(row=0, column=0, sticky="ew")

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

    def _render_scenario_sidebar_placeholder(self, scenario: CampaignGraphScenario, arc: CampaignGraphArc) -> None:
        """Render the sidebar placeholder before the entity browser is ready."""
        container = getattr(self, "_scenario_sidebar_container", None)
        if container is None:
            return

        self._clear_container(container)
        placeholder = ctk.CTkFrame(container, fg_color=DASHBOARD_THEME.panel_bg, corner_radius=20, border_width=1, border_color=DASHBOARD_THEME.card_border)
        placeholder.grid(row=0, column=0, sticky="nsew")
        placeholder.grid_columnconfigure(0, weight=1)
        placeholder.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(
            placeholder,
            text="Scenario entities",
            text_color=DASHBOARD_THEME.text_primary,
            font=ctk.CTkFont(size=18, weight="bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="w", padx=16, pady=(14, 6))
        ctk.CTkLabel(
            placeholder,
            text=f"Preparing the entity roster for {scenario.title} in {arc.name}.",
            text_color=DASHBOARD_THEME.text_secondary,
            font=ctk.CTkFont(size=12),
            anchor="w",
            justify="left",
            wraplength=420,
        ).grid(row=1, column=0, sticky="nw", padx=16, pady=(0, 16))

    def _schedule_scenario_sidebar_render(self, arc: CampaignGraphArc, scenario: CampaignGraphScenario) -> None:
        """Schedule the sidebar browser render after first paint."""
        self._cancel_pending_sidebar_render()
        container = getattr(self, "_scenario_sidebar_container", None)
        if container is None:
            return

        target = (arc.name, scenario.title)
        self._pending_sidebar_target = target

        def _render() -> None:
            """Render the operation."""
            self._pending_sidebar_job = None
            self._pending_sidebar_target = None
            self._render_scenario_sidebar_if_current(target[0], target[1])

        self._pending_sidebar_job = self.after(25, _render)

    def _render_scenario_sidebar_if_current(self, arc_name: str, scenario_title: str) -> None:
        """Render the entity browser only if the selection is still current."""
        payload = self._selected_campaign
        if payload is None:
            return

        selected_arc = self._get_selected_arc(payload)
        if selected_arc is None or selected_arc.name != arc_name:
            return
        if self._selected_scenario_index >= len(selected_arc.scenarios):
            return

        selected_scenario = selected_arc.scenarios[self._selected_scenario_index]
        if selected_scenario.title != scenario_title:
            return

        container = getattr(self, "_scenario_sidebar_container", None)
        if container is None or not hasattr(container, "winfo_exists") or not container.winfo_exists():
            return

        self._clear_container(container)
        ScenarioEntityBrowser(
            container,
            scenario_title=selected_scenario.title,
            links=selected_scenario.entity_links,
            on_open_entity=self._open_entity,
        ).grid(row=0, column=0, sticky="nsew")

    def _cancel_pending_sidebar_render(self) -> None:
        """Cancel any scheduled sidebar render."""
        job = getattr(self, "_pending_sidebar_job", None)
        if job is not None and hasattr(self, "after_cancel"):
            try:
                self.after_cancel(job)
            except Exception:
                pass
        self._pending_sidebar_job = None
        self._pending_sidebar_target = None

    def destroy(self) -> None:
        """Destroy the panel and cancel deferred work first."""
        self._cancel_pending_sidebar_render()
        try:
            super().destroy()
        except Exception:
            pass

    def _get_selected_arc(self, payload: CampaignGraphPayload) -> CampaignGraphArc | None:
        """Return selected arc."""
        if not payload.arcs:
            return None
        return payload.arcs[self._clamp_index(self._selected_arc_index, len(payload.arcs))]

    def _shift_arc(self, step: int) -> None:
        """Internal helper for shift arc."""
        payload = self._selected_campaign
        if payload is None or not payload.arcs:
            return
        self._selected_arc_index = self._clamp_index(self._selected_arc_index + step, len(payload.arcs))
        self._selected_scenario_index = 0
        self._persist_focus_state()
        self._refresh_arc_focus()

    def _shift_scenario(self, step: int) -> None:
        """Internal helper for shift scenario."""
        payload = self._selected_campaign
        selected_arc = self._get_selected_arc(payload) if payload is not None else None
        if selected_arc is None or not selected_arc.scenarios:
            return
        self._selected_scenario_index = self._clamp_index(self._selected_scenario_index + step, len(selected_arc.scenarios))
        self._persist_focus_state()
        self._refresh_scenario_focus()

    def _select_arc(self, index: int) -> None:
        """Select arc."""
        payload = self._selected_campaign
        if payload is None or not payload.arcs:
            return
        self._selected_arc_index = self._clamp_index(index, len(payload.arcs))
        self._selected_scenario_index = 0
        self._persist_focus_state()
        self._refresh_arc_focus()

    def _select_scenario(self, index: int) -> None:
        """Select scenario."""
        payload = self._selected_campaign
        selected_arc = self._get_selected_arc(payload) if payload is not None else None
        if selected_arc is None or not selected_arc.scenarios:
            return
        self._selected_scenario_index = self._clamp_index(index, len(selected_arc.scenarios))
        self._persist_focus_state()
        self._refresh_scenario_focus()

    def _preserve_scroll_position(self, callback) -> None:
        """Internal helper for preserve scroll position."""
        scroll_fraction = self._get_scroll_fraction()
        callback()
        if scroll_fraction is not None:
            self.after_idle(lambda value=scroll_fraction: self._restore_scroll_fraction(value))

    def _get_scroll_fraction(self) -> float | None:
        """Return scroll fraction."""
        canvas = self._get_scroll_canvas()
        if canvas is None or not hasattr(canvas, "yview"):
            return None
        try:
            return float(canvas.yview()[0])
        except Exception:
            return None

    def _restore_scroll_fraction(self, value: float) -> None:
        """Restore scroll fraction."""
        canvas = self._get_scroll_canvas()
        if canvas is None or not hasattr(canvas, "yview_moveto"):
            return
        try:
            canvas.update_idletasks()
            canvas.yview_moveto(value)
        except Exception:
            return

    def _scroll_to_top(self) -> None:
        """Internal helper for scroll to top."""
        self._restore_scroll_fraction(0.0)

    def _get_scroll_canvas(self):
        """Return scroll canvas."""
        scroll = getattr(self, "scroll", None)
        if scroll is None:
            return None

        direct_canvas = getattr(scroll, "_parent_canvas", None)
        if direct_canvas is not None:
            return direct_canvas

        queue = [scroll]
        visited: set[int] = set()
        while queue:
            # Keep looping while queue.
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
        """Internal helper for status color."""
        status = status_label.lower()
        if "completed" in status:
            return DASHBOARD_THEME.arc_complete
        if "link" in status:
            return DASHBOARD_THEME.button_fg
        if "progress" in status:
            return DASHBOARD_THEME.arc_active
        return DASHBOARD_THEME.arc_planned

    def _status_text_color(self, status_label: str) -> str:
        """Internal helper for status text color."""
        if "link" in status_label.lower():
            return DASHBOARD_THEME.text_primary
        return "#f8fbff"

    def refresh_theme(self) -> None:
        """Repaint campaign overview widgets with current theme tokens."""
        self.configure(fg_color=DASHBOARD_THEME.panel_bg)
        if hasattr(self, "scroll"):
            self.scroll.configure(fg_color=DASHBOARD_THEME.panel_bg)
        self._refresh_campaign_content()

    def _clamp_index(self, index: int, length: int) -> int:
        """Internal helper for clamp index."""
        if length <= 0:
            return 0
        return max(0, min(index, length - 1))

    def _bind_wraplength(self, parent, label, *, horizontal_padding: int = 40, minimum: int = 240) -> None:
        """Bind wraplength."""
        def _update(_event=None):
            """Update the operation."""
            try:
                label.configure(wraplength=max(minimum, parent.winfo_width() - horizontal_padding))
            except Exception:
                pass

        parent.bind("<Configure>", _update, add="+")
        parent.after(50, _update)

    def _open_scenario(self, scenario_name: str) -> None:
        """Open scenario."""
        self._open_entity("Scenarios", scenario_name)

    def _open_scenario_gm_screen(self, scenario_name: str) -> None:
        """Open scenario GM screen."""
        scenario_item = next((item for item in self._scenario_items if str(item.get("Title") or "").strip() == scenario_name), None)
        if not isinstance(scenario_item, dict):
            messagebox.showerror("GM screen", f"Scenario '{scenario_name}' could not be loaded.", parent=self.winfo_toplevel())
            return

        def _fallback() -> None:
            """Internal helper for fallback."""
            try:
                # Keep fallback resilient if this step fails.
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
        """Open entity."""
        try:
            open_entity_tab(entity_type, entity_name, self.winfo_toplevel())
        except Exception as exc:
            messagebox.showerror("Open entity", f"Unable to open {entity_type} '{entity_name}':\n{exc}", parent=self.winfo_toplevel())

    def _render_empty_state(self, message: str) -> None:
        """Render empty state."""
        self._empty_state_label.configure(text=message)
        self._empty_state_label.grid(row=0, column=0, sticky="ew", padx=12, pady=24)

    def _hide_empty_state(self) -> None:
        """Hide empty state."""
        self._empty_state_label.grid_forget()

    def _clear_container(self, container) -> None:
        """Clear container."""
        for child in container.winfo_children():
            child.destroy()
