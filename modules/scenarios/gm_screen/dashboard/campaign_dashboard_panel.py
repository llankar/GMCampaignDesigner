from __future__ import annotations

import customtkinter as ctk
import tkinter as tk
from typing import Callable

from .widgets.campaign_arc_field import CampaignArcField
from .campaign_dashboard_data import (
    build_campaign_option_index,
    extract_campaign_fields,
    load_campaign_entities,
)


class CampaignDashboardPanel(ctk.CTkFrame):
    """GM dashboard focused on campaign entities only."""

    def __init__(
        self,
        master,
        *,
        wrappers: dict,
        open_entity_callback: Callable[[str, str], None],
        **kwargs,
    ):
        super().__init__(master, **kwargs)
        self.wrappers = wrappers or {}
        self.open_entity_callback = open_entity_callback

        self._campaign_catalog = load_campaign_entities(self.wrappers)
        self._campaign_options, self._option_to_campaign = build_campaign_option_index(self._campaign_catalog)

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(self, corner_radius=14)
        header.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 6))

        content = ctk.CTkFrame(self, corner_radius=14)
        content.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))

        self._build_header(header)
        self._build_details_content(content)

        if self._campaign_options:
            self.campaign_picker_var.set(self._campaign_options[0])
            self._on_campaign_selected(self._campaign_options[0])

    def _build_header(self, parent: ctk.CTkFrame) -> None:
        parent.grid_columnconfigure(0, weight=2)
        parent.grid_columnconfigure(1, weight=3)

        ctk.CTkLabel(
            parent,
            text="🎬 Campaign Dashboard",
            font=ctk.CTkFont(size=24, weight="bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="ew", padx=16, pady=(12, 4))

        ctk.CTkLabel(
            parent,
            text="Select a campaign to view only campaign entity fields.",
            text_color="gray80",
            anchor="w",
        ).grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 12))

        self._build_campaign_picker(parent)

    def _build_campaign_picker(self, parent: ctk.CTkFrame) -> None:
        selector_wrap = ctk.CTkFrame(parent)
        selector_wrap.grid(row=0, column=1, rowspan=2, sticky="nsew", padx=12, pady=10)
        selector_wrap.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkLabel(
            selector_wrap,
            text="Campaign selector",
            font=ctk.CTkFont(size=14, weight="bold"),
            anchor="w",
        ).grid(row=0, column=0, columnspan=2, sticky="ew", padx=6, pady=(8, 2))

        values = self._campaign_options or ["No campaigns"]
        self.campaign_picker_var = tk.StringVar(value=values[0])
        self.campaign_selector = ctk.CTkOptionMenu(
            selector_wrap,
            variable=self.campaign_picker_var,
            values=values,
            command=self._on_campaign_selected,
        )
        self.campaign_selector.grid(row=1, column=0, sticky="ew", padx=4, pady=(4, 8))

        ctk.CTkButton(
            selector_wrap,
            text="Open campaign tab",
            command=self._open_selected_campaign,
        ).grid(row=1, column=1, sticky="ew", padx=4, pady=(4, 8))

    def _build_details_content(self, parent: ctk.CTkFrame) -> None:
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(2, weight=1)

        ctk.CTkLabel(
            parent,
            text="📖 Campaign Entity Details",
            font=ctk.CTkFont(size=20, weight="bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="ew", padx=16, pady=(14, 6))

        self.entity_meta_label = ctk.CTkLabel(parent, text="", anchor="w", text_color="gray80")
        self.entity_meta_label.grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 8))

        self.details_scroll = ctk.CTkScrollableFrame(parent)
        self.details_scroll.grid(row=2, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self.details_scroll.grid_columnconfigure(0, weight=1)

    def _on_campaign_selected(self, selected_option: str) -> None:
        entry = self._option_to_campaign.get(selected_option)
        for child in self.details_scroll.winfo_children():
            child.destroy()

        if not entry:
            ctk.CTkLabel(
                self.details_scroll,
                text="No campaign selected.",
                text_color="gray70",
                anchor="w",
            ).grid(row=0, column=0, sticky="ew", padx=8, pady=8)
            self.entity_meta_label.configure(text="")
            return

        campaign_name = entry["name"]
        fields = extract_campaign_fields(entry.get("item"))
        self.entity_meta_label.configure(text=f"Campaigns • {campaign_name}")

        if not fields:
            ctk.CTkLabel(
                self.details_scroll,
                text="No displayable fields found for this campaign.",
                text_color="gray70",
                anchor="w",
            ).grid(row=0, column=0, sticky="ew", padx=8, pady=8)
            return

        row = 0
        for field in fields:
            block = ctk.CTkFrame(self.details_scroll, corner_radius=10)
            block.grid(row=row, column=0, sticky="ew", padx=6, pady=5)
            block.grid_columnconfigure(0, weight=1)

            ctk.CTkLabel(
                block,
                text=field["name"],
                font=ctk.CTkFont(size=13, weight="bold"),
                anchor="w",
                text_color="gray85",
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
                            command=lambda et=linked_type, n=value: self.open_entity_callback(et, n),
                        ).grid(row=idx, column=0, sticky="ew", pady=2)
                    else:
                        ctk.CTkLabel(values_wrap, text=f"• {value}", anchor="w").grid(
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
                body = ctk.CTkTextbox(block, height=90, wrap="word")
                body.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 8))
                body.insert("1.0", field.get("value") or "")
                body.configure(state="disabled")
            row += 1

    def _open_selected_campaign(self) -> None:
        selected = self.campaign_picker_var.get()
        entry = self._option_to_campaign.get(selected)
        if not entry:
            return
        self.open_entity_callback("Campaigns", entry["name"])
