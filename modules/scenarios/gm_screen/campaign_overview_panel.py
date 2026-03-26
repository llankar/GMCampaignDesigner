from __future__ import annotations

import math
import customtkinter as ctk
import tkinter as tk
from typing import Callable

from modules.helpers.text_helpers import coerce_text
from .campaign_entity_browser import (
    build_campaign_entity_catalog,
    build_option_index,
    extract_display_fields,
    scenario_label,
)


class CampaignOverviewPanel(ctk.CTkFrame):
    """Campaign-centric dashboard focused on currently linked scenario entities."""

    _COMPACT_VALUE_MAX_LENGTH = 80
    _TEXTBOX_MIN_HEIGHT = 36
    _TEXTBOX_MAX_HEIGHT = 220
    _TEXTBOX_LINE_HEIGHT = 18
    _TEXTBOX_WIDTH_CHARS = 72

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

        self._entity_catalog = build_campaign_entity_catalog(self.wrappers)
        self._entity_options, self._option_to_entity = build_option_index(self._entity_catalog)

        self.grid_columnconfigure(0, weight=3)
        self.grid_columnconfigure(1, weight=2)
        self.grid_rowconfigure(0, weight=1)

        left = ctk.CTkFrame(self, corner_radius=14)
        left.grid(row=0, column=0, sticky="nsew", padx=(12, 6), pady=12)

        right = ctk.CTkFrame(self, corner_radius=14)
        right.grid(row=0, column=1, sticky="nsew", padx=(6, 12), pady=12)

        self._build_left_column(left)
        self._build_right_column(right)

        if self._entity_options:
            self.entity_picker_var.set(self._entity_options[0])
            self._on_entity_selected(self._entity_options[0])

    def _build_left_column(self, parent: ctk.CTkFrame) -> None:
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(5, weight=1)

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

        summary_box = ctk.CTkTextbox(parent, height=120, wrap="word", activate_scrollbars=True)
        summary_box.grid(row=2, column=0, sticky="ew", padx=8)
        summary_box.insert("1.0", summary)
        summary_box.configure(state="disabled")

        self._build_entity_picker(parent)

        linked_frame = ctk.CTkFrame(parent)
        linked_frame.grid(row=5, column=0, sticky="nsew", padx=12, pady=(4, 12))
        linked_frame.grid_columnconfigure(0, weight=1)
        linked_frame.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(
            linked_frame,
            text="🔗 Current campaign quick links",
            font=ctk.CTkFont(size=15, weight="bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 6))

        quick_links = ctk.CTkScrollableFrame(linked_frame, height=220)
        quick_links.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        quick_links.grid_columnconfigure(0, weight=1)
        self._populate_linked_entities(quick_links)

    def _build_entity_picker(self, parent: ctk.CTkFrame) -> None:
        selector_wrap = ctk.CTkFrame(parent)
        selector_wrap.grid(row=3, column=0, sticky="ew", padx=12, pady=(12, 8))
        selector_wrap.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkLabel(
            selector_wrap,
            text="Current campaign entity",
            font=ctk.CTkFont(size=14, weight="bold"),
            anchor="w",
        ).grid(row=0, column=0, columnspan=2, sticky="ew", padx=6, pady=(8, 2))

        values = self._entity_options or ["No linked entities"]
        self.entity_picker_var = tk.StringVar(value=values[0])
        self.entity_selector = ctk.CTkOptionMenu(
            selector_wrap,
            variable=self.entity_picker_var,
            values=values,
            command=self._on_entity_selected,
        )
        self.entity_selector.grid(row=1, column=0, sticky="ew", padx=4, pady=(4, 8))

        ctk.CTkButton(
            selector_wrap,
            text="Open in tab",
            command=self._open_selected_entity,
        ).grid(row=1, column=1, sticky="ew", padx=4, pady=(4, 8))

        cards = ctk.CTkFrame(parent, fg_color="transparent")
        cards.grid(row=4, column=0, sticky="ew", padx=12, pady=(0, 8))
        cards.grid_columnconfigure((0, 1), weight=1)

        for idx, (label, count) in enumerate(self._collect_counts()):
            card = ctk.CTkFrame(cards, corner_radius=12)
            card.grid(row=idx // 2, column=idx % 2, sticky="ew", padx=5, pady=5)
            ctk.CTkLabel(card, text=str(count), font=ctk.CTkFont(size=20, weight="bold")).pack(pady=(10, 0))
            ctk.CTkLabel(card, text=label, text_color="gray70").pack(pady=(0, 10))

    def _build_right_column(self, parent: ctk.CTkFrame) -> None:
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(2, weight=1)

        ctk.CTkLabel(
            parent,
            text="📖 Current Campaign Details",
            font=ctk.CTkFont(size=20, weight="bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="ew", padx=16, pady=(14, 6))

        self.entity_meta_label = ctk.CTkLabel(parent, text="", anchor="w", text_color="gray80")
        self.entity_meta_label.grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 8))

        self.details_scroll = ctk.CTkScrollableFrame(parent)
        self.details_scroll.grid(row=2, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self.details_scroll.grid_columnconfigure(0, weight=1)

    def _on_entity_selected(self, selected_option: str) -> None:
        entry = self._option_to_entity.get(selected_option)
        for child in self.details_scroll.winfo_children():
            child.destroy()

        if not entry:
            ctk.CTkLabel(
                self.details_scroll,
                text="No linked entities in this scenario yet.",
                text_color="gray70",
                anchor="w",
            ).grid(row=0, column=0, sticky="ew", padx=8, pady=8)
            self.entity_meta_label.configure(text="")
            return

        entity_type = entry["entity_type"]
        name = entry["name"]
        item = entry.get("item")
        fields = extract_display_fields(entity_type, item)

        self.entity_meta_label.configure(text=f"{entity_type} • {name}")

        if not fields:
            ctk.CTkLabel(
                self.details_scroll,
                text="No displayable fields found for this entity.",
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
            else:
                self._render_read_only_field(block, field.get("value"))
            row += 1

    def _render_read_only_field(self, parent: ctk.CTkFrame, raw_value: str | None) -> None:
        value = raw_value or ""
        if self._should_use_compact_render(value):
            ctk.CTkLabel(
                parent,
                text=value,
                anchor="w",
                justify="left",
                text_color="gray90",
            ).grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 8))
            return

        textbox_height = self._compute_textbox_height(value)
        body = ctk.CTkTextbox(parent, height=textbox_height, wrap="word", activate_scrollbars=True)
        body.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 8))
        body.insert("1.0", value)
        body.configure(state="disabled")

    def _should_use_compact_render(self, value: str) -> bool:
        return "\n" not in value and len(value) <= self._COMPACT_VALUE_MAX_LENGTH

    def _compute_textbox_height(self, value: str) -> int:
        line_count = max(value.count("\n") + 1, math.ceil(len(value) / self._TEXTBOX_WIDTH_CHARS))
        content_height = line_count * self._TEXTBOX_LINE_HEIGHT
        return max(self._TEXTBOX_MIN_HEIGHT, min(self._TEXTBOX_MAX_HEIGHT, content_height))

    def _open_selected_entity(self) -> None:
        selected = self.entity_picker_var.get()
        entry = self._option_to_entity.get(selected)
        if not entry:
            return
        self.open_entity_callback(entry["entity_type"], entry["name"])

    def _collect_counts(self):
        linked_total = sum(len(self.scenario_item.get(entity_type) or []) for entity_type in self._linked_types())
        cards = [
            ("Scenes", len(self.scenario_item.get("Scenes") or [])),
            ("Linked NPCs", len(self.scenario_item.get("NPCs") or [])),
            ("Linked Places", len(self.scenario_item.get("Places") or [])),
            ("Maps", self.map_count),
            ("Campaign Links", linked_total),
            ("Linked Types", len([t for t in self._linked_types() if self.scenario_item.get(t)])),
        ]
        return cards

    def _linked_types(self) -> list[str]:
        return ["NPCs", "Places", "Clues", "Factions", "Objects", "Creatures", "Villains", "PCs", "Informations", "Books"]

    def _populate_linked_entities(self, parent: ctk.CTkScrollableFrame) -> None:
        preferred_order = self._linked_types()
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
            for name in names[:12]:
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
