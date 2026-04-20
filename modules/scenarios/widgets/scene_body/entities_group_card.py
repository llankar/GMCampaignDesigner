"""Utilities for scenario entities group card."""

from __future__ import annotations

import customtkinter as ctk

from modules.scenarios.widgets.entity_chips import create_entity_chip
from .constants import DEFAULT_VISIBLE_CHIPS

CHIP_HORIZONTAL_GAP = 6
CHIP_VERTICAL_GAP = 6


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

    initial_chips = []
    for entity_payload in initial_entities:
        initial_chips.append(
            create_entity_chip(
                chips_container,
                group_label=group_label,
                entity_payload=entity_payload,
                palette=palette,
                open_entity_callback=open_entity_callback,
            )
        )

    if not hidden_entities:
        _reflow_chips(chips_container, initial_chips)
        chips_container.bind("<Configure>", lambda _event: _reflow_chips(chips_container, initial_chips), add="+")
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

    show_all = False

    def _visible_widgets():
        """Return visible widgets in display order."""
        if show_all:
            return [*initial_chips, *hidden_chips, toggle_button]
        return [*initial_chips, toggle_button]

    def _show_less():
        """Show less."""
        nonlocal show_all
        show_all = False
        toggle_button.configure(text=f"+{len(hidden_chips)} more", command=_show_more)
        _reflow_chips(chips_container, _visible_widgets())

    def _show_more():
        """Show more."""
        nonlocal show_all
        show_all = True
        toggle_button.configure(text="Show less", command=_show_less)
        _reflow_chips(chips_container, _visible_widgets())

    chips_container.bind("<Configure>", lambda _event: _reflow_chips(chips_container, _visible_widgets()), add="+")
    _show_less()
    return card


def _reflow_chips(chips_container, widgets):
    """Reflow chips into a wrapping grid according to container width."""
    if not widgets:
        return

    chips_container.update_idletasks()
    container_width = max(chips_container.winfo_width(), chips_container.winfo_reqwidth(), 1)
    columns = _estimate_columns(container_width, widgets)

    for widget in chips_container.winfo_children():
        try:
            widget.grid_forget()
        except Exception:
            continue

    for index, widget in enumerate(widgets):
        widget.grid(
            row=index // columns,
            column=index % columns,
            padx=(0, CHIP_HORIZONTAL_GAP),
            pady=(0, CHIP_VERTICAL_GAP),
            sticky="w",
        )


def _estimate_columns(container_width, widgets):
    """Estimate how many chips can fit in one row."""
    width_hints = [max(widget.winfo_reqwidth(), 1) for widget in widgets]
    if not width_hints:
        return 1
    average_chip_width = max(80, sum(width_hints) // len(width_hints))
    return max(1, container_width // (average_chip_width + CHIP_HORIZONTAL_GAP))
