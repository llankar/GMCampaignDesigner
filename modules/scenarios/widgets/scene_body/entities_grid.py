"""Utilities for scenario entities grid."""

from __future__ import annotations

import customtkinter as ctk

from .constants import COMPACT_GRID_BREAKPOINT, DEFAULT_VISIBLE_CHIPS
from .entities_group_card import create_entities_group_card


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
        card = create_entities_group_card(
            cards_grid,
            group_label=group_label,
            entities=entities or [],
            palette=palette,
            open_entity_callback=open_entity_callback,
            visible_limit=visible_limit,
        )
        cards.append(card)

    def _apply_layout(_event=None):
        """Apply layout."""
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

