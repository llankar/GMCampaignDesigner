"""Utilities for scenario entities group card."""

from __future__ import annotations

import customtkinter as ctk

from modules.scenarios.widgets.entity_chips import create_entity_chip
from .constants import DEFAULT_VISIBLE_CHIPS


def create_entities_group_card(
    parent,
    *,
    group_label,
    entities,
    palette,
    open_entity_callback=None,
    visible_limit=DEFAULT_VISIBLE_CHIPS,
):
    """Create entities group card."""
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

    if not entities:
        ctk.CTkLabel(
            chips_container,
            text="Aucune entité",
            font=ctk.CTkFont(size=10, slant="italic"),
            text_color=palette["muted_text"],
            anchor="w",
        ).pack(fill="x", pady=(0, 6))
        return card

    max_visible = max(1, int(visible_limit or DEFAULT_VISIBLE_CHIPS))
    initial_entities = entities[:max_visible]
    hidden_entities = entities[max_visible:]

    for entity_payload in initial_entities:
        create_entity_chip(
            chips_container,
            group_label=group_label,
            entity_payload=entity_payload,
            palette=palette,
            open_entity_callback=open_entity_callback,
        ).pack(side="left", padx=(0, 6), pady=(0, 6))

    if not hidden_entities:
        return card

    hidden_chips = []
    for hidden_payload in hidden_entities:
        hidden_chip = create_entity_chip(
            chips_container,
            group_label=group_label,
            entity_payload=hidden_payload,
            palette=palette,
            open_entity_callback=open_entity_callback,
        )
        hidden_chips.append(hidden_chip)

    toggle_button = ctk.CTkButton(
        chips_container,
        text="",
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

    def _pack_toggle_button():
        """Pack toggle button."""
        toggle_button.pack_forget()
        toggle_button.pack(side="left", padx=(0, 6), pady=(0, 6))

    def _show_less():
        """Show less."""
        for hidden_chip in hidden_chips:
            hidden_chip.pack_forget()
        toggle_button.configure(text=f"+{len(hidden_chips)} more", command=_show_more)
        _pack_toggle_button()

    def _show_more():
        """Show more."""
        toggle_button.pack_forget()
        for hidden_chip in hidden_chips:
            hidden_chip.pack(side="left", padx=(0, 6), pady=(0, 6))
        toggle_button.configure(text="Show less", command=_show_less)
        toggle_button.pack(side="left", padx=(0, 6), pady=(0, 6))

    _show_less()
    return card
