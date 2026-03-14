from __future__ import annotations

import math
import customtkinter as ctk
import tkinter as tk
from typing import Callable

from modules.campaigns.shared.arc_parser import coerce_arc_list
from .widgets.campaign_arc_field import CampaignArcField
from .campaign_dashboard_data import (
    build_campaign_option_index,
    extract_campaign_fields,
    load_campaign_entities,
)
from .search.campaign_field_search import build_field_search_index, find_match_ranges, normalize_query
from .session_prep.session_prep_summary import build_session_prep_summary
from .styles.dashboard_theme import DASHBOARD_THEME


class CampaignDashboardPanel(ctk.CTkFrame):
    """GM dashboard focused on campaign entities only."""

    _COMPACT_VALUE_MAX_LENGTH = 80
    _TEXTBOX_MIN_HEIGHT = 36
    _TEXTBOX_MAX_HEIGHT = 120
    _TEXTBOX_LINE_HEIGHT = 18
    _TEXTBOX_WIDTH_CHARS = 72
    _HIGHLIGHT_BG_COLOR = "#61482A"
    _HIGHLIGHT_TEXT_COLOR = "#FFE2AD"

    def __init__(
        self,
        master,
        *,
        wrappers: dict,
        open_entity_callback: Callable[[str, str], None],
        **kwargs,
    ):
        super().__init__(master, fg_color=DASHBOARD_THEME.panel_bg, **kwargs)
        self.wrappers = wrappers or {}
        self.open_entity_callback = open_entity_callback

        self._campaign_catalog = load_campaign_entities(self.wrappers)
        self._campaign_options, self._option_to_campaign = build_campaign_option_index(self._campaign_catalog)
        self._indexed_fields: list[dict] = []

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(self, corner_radius=16, fg_color=DASHBOARD_THEME.panel_alt_bg)
        header.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 6))

        content = ctk.CTkFrame(self, corner_radius=16, fg_color=DASHBOARD_THEME.panel_alt_bg)
        content.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))

        self._build_header(header)
        self._build_details_content(content)

        if self._campaign_options:
            self.campaign_picker_var.set(self._campaign_options[0])
            self._on_campaign_selected(self._campaign_options[0])

    def _build_header(self, parent: ctk.CTkFrame) -> None:
        parent.grid_columnconfigure(0, weight=1)

        self._build_campaign_picker(parent)

    def _make_summary_card(self, parent: ctk.CTkFrame, label: str, value: str) -> ctk.CTkLabel:
        card = ctk.CTkFrame(
            parent,
            corner_radius=12,
            fg_color=DASHBOARD_THEME.card_bg,
            border_width=1,
            border_color=DASHBOARD_THEME.card_border,
        )
        col = {"Campaigns": 0, "Arcs": 1, "Linked scenarios": 2}[label]
        card.grid(row=0, column=col, sticky="ew", padx=4)

        ctk.CTkLabel(
            card,
            text=label,
            text_color=DASHBOARD_THEME.text_secondary,
            anchor="w",
            font=ctk.CTkFont(size=11),
        ).grid(row=0, column=0, padx=10, pady=(8, 2), sticky="w")

        value_label = ctk.CTkLabel(
            card,
            text=value,
            text_color=DASHBOARD_THEME.text_primary,
            anchor="w",
            font=ctk.CTkFont(size=19, weight="bold"),
        )
        value_label.grid(row=1, column=0, padx=10, pady=(0, 8), sticky="w")
        return value_label

    def _build_campaign_picker(self, parent: ctk.CTkFrame) -> None:
        selector_wrap = ctk.CTkFrame(
            parent,
            fg_color=DASHBOARD_THEME.card_bg,
            border_width=1,
            border_color=DASHBOARD_THEME.card_border,
            corner_radius=12,
        )
        selector_wrap.grid(row=0, column=0, rowspan=3, sticky="nswe", padx=12, pady=10)
        selector_wrap.grid_columnconfigure((0, 1), weight=1)
        selector_wrap.grid_columnconfigure(2, weight=0)

        ctk.CTkLabel(
            selector_wrap,
            text="Select a Campaign",
            font=ctk.CTkFont(size=14, weight="bold"),
            anchor="nw",
            text_color=DASHBOARD_THEME.text_primary,
        ).grid(row=0, column=0, columnspan=2, sticky="nsew", padx=10, pady=(10, 2))

        values = self._campaign_options or ["No campaigns"]
        self.campaign_picker_var = tk.StringVar(value=values[0])
        self.campaign_selector = ctk.CTkOptionMenu(
            selector_wrap,
            variable=self.campaign_picker_var,
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
        self.campaign_selector.grid(row=1, column=0, sticky="nsew", padx=6, pady=(4, 10))

        ctk.CTkButton(
            selector_wrap,
            text="Open campaign tab",
            fg_color=DASHBOARD_THEME.accent,
            hover_color=DASHBOARD_THEME.accent_hover,
            command=self._open_selected_campaign,
        ).grid(row=1, column=1, sticky="nsew", padx=6, pady=(4, 10))

        self.session_prep_var = tk.BooleanVar(value=False)
        self.session_prep_toggle = ctk.CTkSwitch(
            selector_wrap,
            text="Session Prep",
            variable=self.session_prep_var,
            command=self._on_session_prep_toggled,
            text_color=DASHBOARD_THEME.text_primary,
            progress_color=DASHBOARD_THEME.accent,
            button_color=DASHBOARD_THEME.input_button,
            button_hover_color=DASHBOARD_THEME.input_hover,
        )
        self.session_prep_toggle.grid(row=1, column=2, sticky="nsew", padx=(4, 10), pady=(4, 10))

    def _build_details_content(self, parent: ctk.CTkFrame) -> None:
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(3, weight=1)

        ctk.CTkLabel(
            parent,
            text="📖 Campaign Details",
            font=ctk.CTkFont(size=20, weight="bold"),
            anchor="w",
            text_color=DASHBOARD_THEME.text_primary,
        ).grid(row=0, column=0, sticky="ew", padx=16, pady=(14, 6))

        self.entity_meta_label = ctk.CTkLabel(
            parent,
            text="",
            anchor="w",
            text_color=DASHBOARD_THEME.text_secondary,
        )
        self.entity_meta_label.grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 8))

        self.search_var = tk.StringVar(value="")
        self.search_var.trace_add("write", lambda *_: self._on_search_changed())

        search_wrap = ctk.CTkFrame(parent, fg_color="transparent")
        search_wrap.grid(row=2, column=0, sticky="ew", padx=16, pady=(0, 8))
        search_wrap.grid_columnconfigure(2, weight=1)

        ctk.CTkLabel(
            search_wrap,
            text="Search fields",
            anchor="w",
            text_color=DASHBOARD_THEME.text_secondary,
        ).grid(row=0, column=0, sticky="w", padx=(0, 8))

        self.search_entry = ctk.CTkEntry(
            search_wrap,
            textvariable=self.search_var,
            placeholder_text="Filter by field name or value...",
            width=360,
            fg_color=DASHBOARD_THEME.input_bg,
            border_color=DASHBOARD_THEME.card_border,
            text_color=DASHBOARD_THEME.text_primary,
        )
        self.search_entry.grid(row=0, column=1, sticky="w")

        self.details_scroll = ctk.CTkScrollableFrame(parent, fg_color=DASHBOARD_THEME.panel_bg)
        self.details_scroll.grid(row=3, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self.details_scroll.grid_columnconfigure(0, weight=1)

    def _on_campaign_selected(self, selected_option: str) -> None:
        entry = self._option_to_campaign.get(selected_option)
        for child in self.details_scroll.winfo_children():
            child.destroy()

        if not entry:
            self._indexed_fields = []
            self._render_empty_state("No campaign selected.")
            self.entity_meta_label.configure(text="")
            return

        campaign_name = entry["name"]
        fields = extract_campaign_fields(entry.get("item"))
        self.entity_meta_label.configure(text=f"Campaigns • {campaign_name}")
        self._indexed_fields = build_field_search_index(fields)
        self._render_filtered_fields()

    def _on_search_changed(self) -> None:
        self._render_filtered_fields()

    def _on_session_prep_toggled(self) -> None:
        self._render_filtered_fields()

    def _render_empty_state(self, message: str) -> None:
        ctk.CTkLabel(
            self.details_scroll,
            text=message,
            text_color=DASHBOARD_THEME.text_secondary,
            anchor="w",
        ).grid(row=0, column=0, sticky="ew", padx=8, pady=8)

    def _render_filtered_fields(self) -> None:
        for child in self.details_scroll.winfo_children():
            child.destroy()

        if not self._indexed_fields:
            self._render_empty_state("No displayable fields found for this campaign.")
            return

        query = normalize_query(self.search_var.get())
        visible_fields = [
            indexed["field"] for indexed in self._indexed_fields if not query or query in indexed["searchable_text"]
        ]

        if self.session_prep_var.get():
            self._render_session_prep_view(visible_fields, query)
            return

        if not visible_fields:
            self._render_empty_state("No field matches your search.")
            return

        row = 0
        for field in visible_fields:
            block = ctk.CTkFrame(
                self.details_scroll,
                corner_radius=12,
                fg_color=DASHBOARD_THEME.card_bg,
                border_width=1,
                border_color=DASHBOARD_THEME.card_border,
            )
            block.grid(row=row, column=0, sticky="ew", padx=6, pady=5)
            block.grid_columnconfigure(0, weight=1)

            ctk.CTkLabel(
                block,
                text=field["name"],
                font=ctk.CTkFont(size=13, weight="bold"),
                anchor="w",
                text_color=DASHBOARD_THEME.text_primary,
            ).grid(row=0, column=0, sticky="ew", padx=10, pady=(8, 2))

            if field["type"] == "list":
                values_wrap = ctk.CTkFrame(block, fg_color="transparent")
                values_wrap.grid(row=1, column=0, sticky="ew", padx=8, pady=(0, 8))
                values_wrap.grid_columnconfigure(0, weight=1)
                linked_type = field.get("linked_type")
                for idx, value in enumerate(field.get("values", [])):
                    if linked_type:
                        ctk.CTkButton(
                            values_wrap,
                            text=f"Open {value}",
                            anchor="w",
                            fg_color=DASHBOARD_THEME.button_fg,
                            hover_color=DASHBOARD_THEME.button_hover,
                            text_color=DASHBOARD_THEME.text_primary,
                            command=lambda et=linked_type, n=value: self.open_entity_callback(et, n),
                        ).grid(row=idx, column=0, sticky="ew", pady=2)
                    else:
                        ctk.CTkLabel(
                            values_wrap,
                            text=f"• {value}",
                            anchor="w",
                            text_color=DASHBOARD_THEME.text_secondary,
                        ).grid(
                            row=idx,
                            column=0,
                            sticky="ew",
                            pady=1,
                        )
            elif field["name"] == "Arcs":
                arc_field = CampaignArcField(
                    block,
                    raw_value=field.get("value"),
                    open_scenario_callback=lambda scenario_name: self.open_entity_callback("Scenarios", scenario_name),
                )
                arc_field.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 8))
            else:
                self._render_read_only_field(block, field.get("value"), query)
            row += 1

    def _render_session_prep_view(self, visible_fields: list[dict], query: str) -> None:
        summary = build_session_prep_summary(visible_fields)

        prep_sections = [
            ("Objectifs actifs", summary.active_objectives),
            ("Arcs in-progress", summary.in_progress_arcs),
            ("Rappels PNJ/Lieux critiques", summary.critical_reminders),
        ]

        row = 0
        for title, lines in prep_sections:
            if query and not lines:
                continue

            block = ctk.CTkFrame(
                self.details_scroll,
                corner_radius=12,
                fg_color=DASHBOARD_THEME.card_bg,
                border_width=1,
                border_color=DASHBOARD_THEME.card_border,
            )
            block.grid(row=row, column=0, sticky="ew", padx=6, pady=5)
            block.grid_columnconfigure(0, weight=1)

            ctk.CTkLabel(
                block,
                text=title,
                font=ctk.CTkFont(size=13, weight="bold"),
                anchor="w",
                text_color=DASHBOARD_THEME.text_primary,
            ).grid(row=0, column=0, sticky="ew", padx=10, pady=(8, 2))

            if not lines:
                ctk.CTkLabel(
                    block,
                    text="Aucune donnée prioritaire trouvée.",
                    anchor="w",
                    text_color=DASHBOARD_THEME.text_secondary,
                ).grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 8))
                row += 1
                continue

            for idx, line in enumerate(lines, start=1):
                line_wrap = ctk.CTkFrame(block, fg_color="transparent")
                line_wrap.grid(row=idx, column=0, sticky="ew", padx=10, pady=(0, 6))
                self._render_highlighted_line(line_wrap, f"• {line}", query)

            row += 1

        if row == 0:
            self._render_empty_state("No field matches your search.")

    def _render_read_only_field(self, parent: ctk.CTkFrame, raw_value: str | None, query: str) -> None:
        value = raw_value or ""
        if self._should_use_compact_render(value):
            self._render_compact_with_highlight(parent, value, query)
            return

        textbox_height = self._compute_textbox_height(value)
        body = ctk.CTkTextbox(
            parent,
            height=textbox_height,
            wrap="word",
            fg_color=DASHBOARD_THEME.panel_bg,
            border_width=1,
            border_color=DASHBOARD_THEME.card_border,
            text_color=DASHBOARD_THEME.text_secondary,
        )
        body.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 8))
        body.insert("1.0", value)
        self._highlight_textbox_matches(body, value, query)
        body.configure(state="disabled")

    def _render_compact_with_highlight(self, parent: ctk.CTkFrame, value: str, query: str) -> None:
        content_wrap = ctk.CTkFrame(parent, fg_color="transparent")
        content_wrap.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 8))
        self._render_highlighted_line(content_wrap, value, query)

    def _render_highlighted_line(self, parent: ctk.CTkFrame, value: str, query: str) -> None:
        ranges = find_match_ranges(value, query)
        if not ranges:
            ctk.CTkLabel(
                parent,
                text=value,
                anchor="w",
                justify="left",
                text_color=DASHBOARD_THEME.text_secondary,
            ).pack(side="left", fill="x", expand=True)
            return

        cursor = 0
        for start, end in ranges:
            if start > cursor:
                ctk.CTkLabel(
                    parent,
                    text=value[cursor:start],
                    anchor="w",
                    justify="left",
                    text_color=DASHBOARD_THEME.text_secondary,
                ).pack(side="left")

            ctk.CTkLabel(
                parent,
                text=value[start:end],
                anchor="w",
                justify="left",
                text_color=self._HIGHLIGHT_TEXT_COLOR,
                fg_color=self._HIGHLIGHT_BG_COLOR,
                corner_radius=4,
            ).pack(side="left", padx=1)
            cursor = end

        if cursor < len(value):
            ctk.CTkLabel(
                parent,
                text=value[cursor:],
                anchor="w",
                justify="left",
                text_color=DASHBOARD_THEME.text_secondary,
            ).pack(side="left")

    def _highlight_textbox_matches(self, textbox: ctk.CTkTextbox, value: str, query: str) -> None:
        ranges = find_match_ranges(value, query)
        if not ranges:
            return

        textbox.tag_config("search_match", background=self._HIGHLIGHT_BG_COLOR, foreground=self._HIGHLIGHT_TEXT_COLOR)
        for start, end in ranges:
            textbox.tag_add("search_match", f"1.0+{start}c", f"1.0+{end}c")

    def _should_use_compact_render(self, value: str) -> bool:
        return "\n" not in value and len(value) <= self._COMPACT_VALUE_MAX_LENGTH

    def _compute_textbox_height(self, value: str) -> int:
        line_count = max(value.count("\n") + 1, math.ceil(len(value) / self._TEXTBOX_WIDTH_CHARS))
        content_height = line_count * self._TEXTBOX_LINE_HEIGHT
        return max(self._TEXTBOX_MIN_HEIGHT, min(self._TEXTBOX_MAX_HEIGHT, content_height))

    def _open_selected_campaign(self) -> None:
        selected = self.campaign_picker_var.get()
        entry = self._option_to_campaign.get(selected)
        if not entry:
            return
        self.open_entity_callback("Campaigns", entry["name"])
