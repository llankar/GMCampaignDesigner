from __future__ import annotations

import customtkinter as ctk
import tkinter as tk
from typing import Callable


_DEFAULT_ENTITY_LABELS = {
    "Scenarios": "Title",
    "Informations": "Title",
    "Books": "Title",
}


class CampaignOverviewPanel(ctk.CTkFrame):
    """Fast, searchable campaign dashboard for the GM screen."""

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

        self.grid_columnconfigure(0, weight=2)
        self.grid_columnconfigure(1, weight=3)
        self.grid_rowconfigure(0, weight=1)

        self._search_items = []

        left = ctk.CTkFrame(self, corner_radius=14)
        left.grid(row=0, column=0, sticky="nsew", padx=(12, 6), pady=12)

        right = ctk.CTkFrame(self, corner_radius=14)
        right.grid(row=0, column=1, sticky="nsew", padx=(6, 12), pady=12)

        self._build_left_column(left)
        self._build_right_column(right)

    def _build_left_column(self, parent: ctk.CTkFrame) -> None:
        parent.grid_columnconfigure(0, weight=1)

        title = self.scenario_item.get("Title") or self.scenario_item.get("Name") or "Scenario"
        summary = (self.scenario_item.get("Summary") or "No summary for this scenario yet.").strip()

        ctk.CTkLabel(
            parent,
            text="🎬 Session Dashboard",
            font=ctk.CTkFont(size=24, weight="bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="ew", padx=16, pady=(14, 4))

        ctk.CTkLabel(
            parent,
            text=title,
            font=ctk.CTkFont(size=18, weight="bold"),
            anchor="w",
        ).grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 10))

        summary_box = ctk.CTkTextbox(parent, height=120, wrap="word")
        summary_box.grid(row=2, column=0, sticky="ew", padx=16)
        summary_box.insert("1.0", summary)
        summary_box.configure(state="disabled")

        cards = ctk.CTkFrame(parent, fg_color="transparent")
        cards.grid(row=3, column=0, sticky="ew", padx=12, pady=(12, 8))
        cards.grid_columnconfigure((0, 1), weight=1)

        counts = self._collect_counts()
        for idx, (label, count) in enumerate(counts):
            card = ctk.CTkFrame(cards, corner_radius=12)
            card.grid(row=idx // 2, column=idx % 2, sticky="ew", padx=5, pady=5)
            ctk.CTkLabel(card, text=str(count), font=ctk.CTkFont(size=20, weight="bold")).pack(pady=(10, 0))
            ctk.CTkLabel(card, text=label, text_color="gray70").pack(pady=(0, 10))

        linked_frame = ctk.CTkFrame(parent)
        linked_frame.grid(row=4, column=0, sticky="nsew", padx=12, pady=(4, 12))
        linked_frame.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(4, weight=1)

        ctk.CTkLabel(
            linked_frame,
            text="Quick links from this scenario",
            font=ctk.CTkFont(size=15, weight="bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 6))

        quick_links = ctk.CTkScrollableFrame(linked_frame, height=230)
        quick_links.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        quick_links.grid_columnconfigure(0, weight=1)

        self._populate_linked_entities(quick_links)

    def _build_right_column(self, parent: ctk.CTkFrame) -> None:
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(2, weight=1)

        ctk.CTkLabel(
            parent,
            text="⚡ GM Quick Finder",
            font=ctk.CTkFont(size=20, weight="bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="ew", padx=16, pady=(14, 4))

        self.search_var = tk.StringVar(value="")
        search_entry = ctk.CTkEntry(
            parent,
            textvariable=self.search_var,
            placeholder_text="Search NPC, place, clue, faction...",
        )
        search_entry.grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 10))
        search_entry.bind("<KeyRelease>", lambda _e: self._refresh_search_results())

        list_frame = ctk.CTkScrollableFrame(parent)
        list_frame.grid(row=2, column=0, sticky="nsew", padx=10, pady=(0, 10))
        list_frame.grid_columnconfigure(0, weight=1)
        self.result_frame = list_frame

        hint = ctk.CTkLabel(
            parent,
            text="Tip: use this panel during play to jump to any important element in one click.",
            text_color="gray70",
            anchor="w",
        )
        hint.grid(row=3, column=0, sticky="ew", padx=16, pady=(0, 12))

        self._build_search_index()
        self._refresh_search_results()

    def _collect_counts(self):
        cards = []
        cards.append(("Scenes", len(self.scenario_item.get("Scenes") or [])))
        cards.append(("Linked NPCs", len(self.scenario_item.get("NPCs") or [])))
        cards.append(("Linked Places", len(self.scenario_item.get("Places") or [])))
        cards.append(("Maps", self.map_count))

        total_entities = 0
        for entity_type, wrapper in self.wrappers.items():
            if entity_type == "Scenarios":
                continue
            try:
                total_entities += len(wrapper.load_items())
            except Exception:
                continue
        cards.append(("Campaign Entities", total_entities))
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
                text="No linked entities yet in this scenario. Add links to unlock one-click navigation.",
                text_color="gray70",
                justify="left",
                wraplength=320,
            ).grid(row=0, column=0, sticky="ew", padx=4, pady=10)

    def _build_search_index(self):
        focus_types = ["NPCs", "Places", "Clues", "Factions", "Villains", "Creatures", "Objects", "Informations", "Books"]
        index = []
        for entity_type in focus_types:
            wrapper = self.wrappers.get(entity_type)
            if wrapper is None:
                continue
            try:
                items = wrapper.load_items()
            except Exception:
                continue
            label_key = _DEFAULT_ENTITY_LABELS.get(entity_type, "Name")
            for item in items:
                label = (item.get(label_key) or "").strip()
                if not label:
                    continue
                searchable = f"{label} {entity_type}".lower()
                index.append({"entity_type": entity_type, "label": label, "searchable": searchable})
        self._search_items = sorted(index, key=lambda x: x["label"].lower())

    def _refresh_search_results(self):
        for child in self.result_frame.winfo_children():
            child.destroy()

        term = (self.search_var.get() or "").strip().lower()
        results = self._search_items
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

        for idx, item in enumerate(results[:120]):
            btn = ctk.CTkButton(
                self.result_frame,
                text=f"{item['label']}  ·  {item['entity_type']}",
                anchor="w",
                command=lambda et=item["entity_type"], name=item["label"]: self.open_entity_callback(et, name),
            )
            btn.grid(row=idx, column=0, sticky="ew", padx=6, pady=3)
