from __future__ import annotations

import customtkinter as ctk
import tkinter as tk
from typing import Callable

from modules.helpers.text_helpers import coerce_text
from .dashboard_presenter import build_entity_picker_data, build_search_index, group_results, scenario_label

_ENTITY_ORDER = ["NPCs", "Places", "Clues", "Factions", "Villains", "Creatures", "Objects", "Informations", "Books", "PCs"]


class CampaignOverviewPanel(ctk.CTkFrame):
    """Campaign-centric dashboard with quick access for GMs."""

    def __init__(
        self,
        master,
        *,
        scenario_item: dict,
        wrappers: dict,
        open_entity_callback: Callable[[str, str], None],
        map_count: int = 0,
        **kwargs,
    ):
        super().__init__(master, **kwargs)
        self.scenario_item = scenario_item or {}
        self.wrappers = wrappers or {}
        self.open_entity_callback = open_entity_callback
        self.map_count = int(map_count or 0)

        self._search_items, self._entity_counts = build_search_index(self.wrappers)
        self._picker_data = build_entity_picker_data(self._search_items)

        self.grid_columnconfigure(0, weight=2)
        self.grid_columnconfigure(1, weight=3)
        self.grid_rowconfigure(0, weight=1)

        left = ctk.CTkFrame(self, corner_radius=14)
        left.grid(row=0, column=0, sticky="nsew", padx=(12, 6), pady=12)

        right = ctk.CTkFrame(self, corner_radius=14)
        right.grid(row=0, column=1, sticky="nsew", padx=(6, 12), pady=12)

        self._build_left_column(left)
        self._build_right_column(right)
        self._refresh_search_results()

    def _build_left_column(self, parent: ctk.CTkFrame) -> None:
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(4, weight=1)

        ctk.CTkLabel(
            parent,
            text="🎬 GM Campaign Command",
            font=ctk.CTkFont(size=24, weight="bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="ew", padx=16, pady=(14, 2))

        scenario_name = scenario_label(self.scenario_item)
        summary = coerce_text(self.scenario_item.get("Summary")).strip() or "No summary for this scenario yet."

        ctk.CTkLabel(
            parent,
            text=scenario_name,
            font=ctk.CTkFont(size=18, weight="bold"),
            anchor="w",
        ).grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 8))

        summary_box = ctk.CTkTextbox(parent, height=120, wrap="word")
        summary_box.grid(row=2, column=0, sticky="ew", padx=16)
        summary_box.insert("1.0", summary)
        summary_box.configure(state="disabled")

        cards = ctk.CTkFrame(parent, fg_color="transparent")
        cards.grid(row=3, column=0, sticky="ew", padx=12, pady=(12, 8))
        cards.grid_columnconfigure((0, 1), weight=1)

        for idx, (label, count) in enumerate(self._collect_counts()):
            card = ctk.CTkFrame(cards, corner_radius=12)
            card.grid(row=idx // 2, column=idx % 2, sticky="ew", padx=5, pady=5)
            ctk.CTkLabel(card, text=str(count), font=ctk.CTkFont(size=20, weight="bold")).pack(pady=(10, 0))
            ctk.CTkLabel(card, text=label, text_color="gray70").pack(pady=(0, 10))

        linked_frame = ctk.CTkFrame(parent)
        linked_frame.grid(row=4, column=0, sticky="nsew", padx=12, pady=(4, 12))
        linked_frame.grid_columnconfigure(0, weight=1)
        linked_frame.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(
            linked_frame,
            text="🔗 Scenario quick links",
            font=ctk.CTkFont(size=15, weight="bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 6))

        quick_links = ctk.CTkScrollableFrame(linked_frame, height=220)
        quick_links.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        quick_links.grid_columnconfigure(0, weight=1)
        self._populate_linked_entities(quick_links)

    def _build_right_column(self, parent: ctk.CTkFrame) -> None:
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(3, weight=1)

        ctk.CTkLabel(
            parent,
            text="⚡ Campaign Intel Finder",
            font=ctk.CTkFont(size=20, weight="bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="ew", padx=16, pady=(14, 4))

        selector_wrap = ctk.CTkFrame(parent)
        selector_wrap.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 8))
        selector_wrap.grid_columnconfigure((0, 1, 2), weight=1)

        self.entity_type_var = tk.StringVar(value="All entities")
        available_types = ["All entities"] + [et for et in _ENTITY_ORDER if et in self._picker_data]
        self.entity_type_selector = ctk.CTkOptionMenu(
            selector_wrap,
            variable=self.entity_type_var,
            values=available_types,
            command=self._on_entity_type_change,
        )
        self.entity_type_selector.grid(row=0, column=0, sticky="ew", padx=4, pady=4)

        self.entity_var = tk.StringVar(value="Select entity")
        self.entity_selector = ctk.CTkOptionMenu(
            selector_wrap,
            variable=self.entity_var,
            values=["Select entity"],
            command=lambda _value: None,
        )
        self.entity_selector.grid(row=0, column=1, sticky="ew", padx=4, pady=4)

        ctk.CTkButton(
            selector_wrap,
            text="Open",
            command=self._open_selected_entity,
        ).grid(row=0, column=2, sticky="ew", padx=4, pady=4)

        self.search_var = tk.StringVar(value="")
        search_entry = ctk.CTkEntry(
            parent,
            textvariable=self.search_var,
            placeholder_text="Search inside selected campaign entities...",
        )
        search_entry.grid(row=2, column=0, sticky="ew", padx=16, pady=(0, 10))
        search_entry.bind("<KeyRelease>", lambda _e: self._refresh_search_results())

        self.result_frame = ctk.CTkScrollableFrame(parent)
        self.result_frame.grid(row=3, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self.result_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            parent,
            text="Use type + entity selectors to jump instantly, or search to scan the campaign.",
            text_color="gray70",
            anchor="w",
        ).grid(row=4, column=0, sticky="ew", padx=16, pady=(0, 12))

        self._on_entity_type_change(self.entity_type_var.get())

    def _on_entity_type_change(self, selected_type: str) -> None:
        if selected_type == "All entities":
            combined = []
            for et in _ENTITY_ORDER:
                combined.extend(self._picker_data.get(et, []))
            values = sorted(set(combined), key=str.lower)
        else:
            values = self._picker_data.get(selected_type, [])

        if not values:
            values = ["No entities"]
        self.entity_selector.configure(values=values)
        self.entity_var.set(values[0])
        self._refresh_search_results()

    def _open_selected_entity(self) -> None:
        entity_name = (self.entity_var.get() or "").strip()
        entity_type = self.entity_type_var.get()
        if not entity_name or entity_name == "No entities":
            return

        if entity_type != "All entities":
            self.open_entity_callback(entity_type, entity_name)
            return

        for item in self._search_items:
            if item["label"] == entity_name:
                self.open_entity_callback(item["entity_type"], entity_name)
                return

    def _collect_counts(self):
        cards = [
            ("Scenes", len(self.scenario_item.get("Scenes") or [])),
            ("Linked NPCs", len(self.scenario_item.get("NPCs") or [])),
            ("Linked Places", len(self.scenario_item.get("Places") or [])),
            ("Maps", self.map_count),
            ("Campaign Entities", sum(self._entity_counts.values())),
            ("Entity Types", len([k for k in self._entity_counts if self._entity_counts.get(k, 0) > 0])),
        ]
        return cards

    def _populate_linked_entities(self, parent: ctk.CTkScrollableFrame) -> None:
        preferred_order = ["NPCs", "Places", "Clues", "Factions", "Objects", "Creatures", "Villains", "PCs"]
        row = 0
        has_any = False
        for entity_type in preferred_order:
            names = self.scenario_item.get(entity_type) or []
            if not names:
                continue
            has_any = True
            ctk.CTkLabel(parent, text=entity_type, anchor="w", font=ctk.CTkFont(weight="bold")).grid(
                row=row,
                column=0,
                sticky="ew",
                pady=(6, 2),
            )
            row += 1
            for name in names[:8]:
                ctk.CTkButton(
                    parent,
                    text=f"Open {name}",
                    anchor="w",
                    command=lambda et=entity_type, n=name: self.open_entity_callback(et, n),
                ).grid(row=row, column=0, sticky="ew", pady=2)
                row += 1

        if not has_any:
            ctk.CTkLabel(
                parent,
                text="No linked entities in this scenario yet. Add links to unlock one-click navigation.",
                text_color="gray70",
                justify="left",
                wraplength=320,
            ).grid(row=0, column=0, sticky="ew", padx=4, pady=10)

    def _refresh_search_results(self):
        for child in self.result_frame.winfo_children():
            child.destroy()

        selected_type = self.entity_type_var.get()
        term = (self.search_var.get() or "").strip().lower()

        results = self._search_items
        if selected_type != "All entities":
            results = [item for item in results if item["entity_type"] == selected_type]
        if term:
            results = [item for item in results if term in item["searchable"]]

        if not results:
            ctk.CTkLabel(self.result_frame, text="No results.", text_color="gray70").grid(
                row=0,
                column=0,
                sticky="w",
                padx=8,
                pady=8,
            )
            return

        grouped = group_results(results[:180])
        row = 0
        for entity_type in _ENTITY_ORDER:
            items = grouped.get(entity_type)
            if not items:
                continue
            ctk.CTkLabel(
                self.result_frame,
                text=f"{entity_type} ({len(items)})",
                anchor="w",
                font=ctk.CTkFont(size=14, weight="bold"),
            ).grid(row=row, column=0, sticky="ew", padx=8, pady=(8, 2))
            row += 1
            for item in items[:20]:
                ctk.CTkButton(
                    self.result_frame,
                    text=item["label"],
                    anchor="w",
                    command=lambda et=item["entity_type"], name=item["label"]: self.open_entity_callback(et, name),
                ).grid(row=row, column=0, sticky="ew", padx=6, pady=2)
                row += 1
