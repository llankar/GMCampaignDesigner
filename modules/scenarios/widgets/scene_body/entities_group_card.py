"""Utilities for scenario entities group card."""

from __future__ import annotations

import customtkinter as ctk

from modules.scenarios.widgets.entity_chips import create_entity_chip
from .constants import DEFAULT_VISIBLE_CHIPS


CHIP_GAP_X = 6
CHIP_GAP_Y = 6
FALLBACK_CHIP_WIDTH = 120


def _estimate_columns(container_width: int, widgets) -> int:
    """Estimate how many chips can fit in a single row."""
    if container_width <= 0:
        return 1
    sample_widths = []
    for widget in widgets:
        try:
            width = int(widget.winfo_reqwidth())
        except Exception:
            width = 0
        if width > 0:
            sample_widths.append(width)
    if not sample_widths:
        return 1
    average_width = max(FALLBACK_CHIP_WIDTH, int(sum(sample_widths) / len(sample_widths)))
    per_chip = max(1, average_width + CHIP_GAP_X)
    return max(1, container_width // per_chip)


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
        initial_chip = create_entity_chip(
            chips_container,
            group_label=group_label,
            entity_payload=entity_payload,
            palette=palette,
            open_entity_callback=open_entity_callback,
        )
        initial_chips.append(initial_chip)

    hidden_chips = []
    for hidden_payload in hidden_entities:
        hidden_chips.append(
            create_entity_chip(
                chips_container,
                group_label=group_label,
                entity_payload=hidden_payload,
                palette=palette,
                open_entity_callback=open_entity_callback,
            )
        )

    toggle_button = None
    is_expanded = False
    if hidden_chips:
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

    all_widgets = [*initial_chips, *hidden_chips]
    if toggle_button is not None:
        all_widgets.append(toggle_button)

    def _visible_widgets():
        """Return widgets visible in current state."""
        if is_expanded:
            visible = [*initial_chips, *hidden_chips]
        else:
            visible = [*initial_chips]
        if toggle_button is not None:
            visible.append(toggle_button)
        return visible

    def _reflow_chips(_event=None):
        """Place chips in a wrapping grid based on container width."""
        if not chips_container.winfo_exists():
            return
        width = int(chips_container.winfo_width() or 0)
        visible_widgets = _visible_widgets()
        for widget in all_widgets:
            widget.grid_forget()
        if not visible_widgets:
            return

        columns = _estimate_columns(width, visible_widgets)
        for col in range(columns):
            chips_container.grid_columnconfigure(col, weight=0)

        for index, widget in enumerate(visible_widgets):
            row = index // columns
            col = index % columns
            widget.grid(row=row, column=col, sticky="w", padx=(0, CHIP_GAP_X), pady=(0, CHIP_GAP_Y))

    def _show_less():
        """Show less."""
        nonlocal is_expanded
        is_expanded = False
        if toggle_button is not None:
            toggle_button.configure(text=f"+{len(hidden_chips)} more", command=_show_more)
        _reflow_chips()

    def _show_more():
        """Show more."""
        nonlocal is_expanded
        is_expanded = True
        if toggle_button is not None:
            toggle_button.configure(text="Show less", command=_show_less)
        _reflow_chips()

    chips_container.bind("<Configure>", _reflow_chips, add="+")
    chips_container.after_idle(_reflow_chips)

    if hidden_chips:
        _show_less()
    return card
