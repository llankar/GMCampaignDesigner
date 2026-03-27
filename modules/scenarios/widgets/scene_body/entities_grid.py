from __future__ import annotations

import customtkinter as ctk


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
    for group_label, names in groups:
        normalized_names = [str(name).strip() for name in names if str(name).strip()]
        if not normalized_names:
            continue
        card = _create_group_card(
            cards_grid,
            group_label=group_label,
            names=normalized_names,
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


def _create_group_card(parent, *, group_label, names, palette, open_entity_callback=None, visible_limit=DEFAULT_VISIBLE_CHIPS):
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
        text=group_label,
        font=ctk.CTkFont(size=11, weight="bold"),
        text_color=palette["text"],
    ).pack(side="left", anchor="w")
    ctk.CTkLabel(
        header,
        text=str(len(names)),
        font=ctk.CTkFont(size=10, weight="bold"),
        text_color=palette["muted_text"],
        fg_color=palette["pill_bg"],
        corner_radius=999,
        padx=8,
        pady=2,
    ).pack(side="right", anchor="e")

    chips_container = ctk.CTkFrame(card, fg_color="transparent")
    chips_container.pack(fill="x", padx=10, pady=(0, 8))

    max_visible = max(1, int(visible_limit or DEFAULT_VISIBLE_CHIPS))
    initial_names = names[:max_visible]
    hidden_names = names[max_visible:]

    for entity_name in initial_names:
        _create_entity_chip(
            chips_container,
            group_label=group_label,
            entity_name=entity_name,
            open_entity_callback=open_entity_callback,
        ).pack(side="left", padx=(0, 6), pady=(0, 6))

    if hidden_names:
        overflow_button = ctk.CTkButton(
            chips_container,
            text=f"+{len(hidden_names)}",
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
            for hidden_name in hidden_names:
                _create_entity_chip(
                    chips_container,
                    group_label=group_label,
                    entity_name=hidden_name,
                    open_entity_callback=open_entity_callback,
                ).pack(side="left", padx=(0, 6), pady=(0, 6))

        overflow_button.configure(command=_show_remaining)

    return card


def _create_entity_chip(parent, *, group_label, entity_name, open_entity_callback=None):
    from modules.generic.detail_ui import create_chip

    chip = create_chip(parent, entity_name)
    if not callable(open_entity_callback):
        return chip

    chip.configure(cursor="hand2")
    for child in chip.winfo_children():
        child.configure(cursor="hand2")

    def _open_entity(_event=None):
        open_entity_callback(group_label, entity_name)

    chip.bind("<Button-1>", _open_entity)
    for child in chip.winfo_children():
        child.bind("<Button-1>", _open_entity)
    return chip
