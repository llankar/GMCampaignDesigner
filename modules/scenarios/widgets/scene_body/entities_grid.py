from __future__ import annotations

import customtkinter as ctk

from modules.scenarios.widgets.entity_chips import create_entity_chip


COMPACT_GRID_BREAKPOINT = 760
DEFAULT_VISIBLE_CHIPS = 6


def create_entities_groups_grid(
    parent,
    *,
    groups,
    palette,
    open_entity_callback=None,
    visible_limit: int = DEFAULT_VISIBLE_CHIPS,
    breakpoint: int = COMPACT_GRID_BREAKPOINT,
):
    """Build a responsive entities grid (2 columns wide / 1 column narrow)."""

    cards_grid = ctk.CTkFrame(parent, fg_color="transparent")
    cards_grid.pack(fill="x", padx=14, pady=(0, 10))

    cards = []
    for group_label, entities in groups:
        card = _create_group_card(
            cards_grid,
            group_label=group_label,
            entities=entities or [],
            palette=palette,
            open_entity_callback=open_entity_callback,
            visible_limit=visible_limit,
        )
        cards.append(card)

    def _apply_layout(_event=None):
        if not cards_grid.winfo_exists():
            return
        try:
            width = int(cards_grid.winfo_width())
        except Exception:
            width = 0
        columns = 1 if width < breakpoint else 2

        for col in range(2):
            cards_grid.grid_columnconfigure(col, weight=0)
        for col in range(columns):
            cards_grid.grid_columnconfigure(col, weight=1, uniform="entity-groups")

        for index, card in enumerate(cards):
            row = index // columns
            col = index % columns
            card.grid(row=row, column=col, sticky="nsew", padx=4, pady=4)

    cards_grid.bind("<Configure>", _apply_layout, add="+")
    cards_grid.after_idle(_apply_layout)
    return cards_grid


def _create_group_card(parent, *, group_label, entities, palette, open_entity_callback=None, visible_limit=DEFAULT_VISIBLE_CHIPS):
    card = ctk.CTkFrame(
        parent,
        fg_color=palette["surface_overlay"],
        corner_radius=14,
        border_width=1,
        border_color=palette["pill_border"],
    )

    header = ctk.CTkFrame(card, fg_color="transparent")
    header.pack(fill="x", padx=10, pady=(10, 6))
    ctk.CTkLabel(
        header,
        text=f"{group_label} ({len(entities)})",
        font=ctk.CTkFont(size=11, weight="bold"),
        text_color=palette["text"],
    ).pack(side="left", anchor="w")

    chips_container = ctk.CTkFrame(card, fg_color="transparent")
    chips_container.pack(fill="x", padx=10, pady=(0, 8))

    max_visible = max(1, int(visible_limit or DEFAULT_VISIBLE_CHIPS))
    initial_entities = entities[:max_visible]
    hidden_entities = entities[max_visible:]

    if not entities:
        ctk.CTkLabel(
            chips_container,
            text="Aucune entité",
            font=ctk.CTkFont(size=10, slant="italic"),
            text_color=palette["muted_text"],
            anchor="w",
        ).pack(fill="x", pady=(0, 6))
        return card

    for entity_payload in initial_entities:
        create_entity_chip(
            chips_container,
            group_label=group_label,
            entity_payload=entity_payload,
            palette=palette,
            open_entity_callback=open_entity_callback,
        ).pack(side="left", padx=(0, 6), pady=(0, 6))

    if hidden_entities:
        overflow_button = ctk.CTkButton(
            chips_container,
            text=f"+{len(hidden_entities)}",
            width=0,
            height=28,
            corner_radius=999,
            fg_color=palette["pill_bg"],
            hover_color=palette["surface_card"],
            text_color=palette["muted_text"],
            border_width=1,
            border_color=palette["pill_border"],
            font=ctk.CTkFont(size=12, weight="bold"),
        )
        overflow_button.pack(side="left", padx=(0, 6), pady=(0, 6))

        def _show_remaining():
            overflow_button.destroy()
            for hidden_payload in hidden_entities:
                create_entity_chip(
                    chips_container,
                    group_label=group_label,
                    entity_payload=hidden_payload,
                    palette=palette,
                    open_entity_callback=open_entity_callback,
                ).pack(side="left", padx=(0, 6), pady=(0, 6))

        overflow_button.configure(command=_show_remaining)

    return card
