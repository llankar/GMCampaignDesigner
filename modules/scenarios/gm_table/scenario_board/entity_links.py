"""Reusable linked entity lists for the Scenario Board."""

from __future__ import annotations

from collections.abc import Callable, Iterable

import customtkinter as ctk

from modules.scenarios.gm_table.scenario_board.styles import BOARD_TEXT

OpenEntityCallback = Callable[[str, str], None]


def add_entity_links(
    parent,
    entries: Iterable[tuple[str, str]],
    callback: OpenEntityCallback | None,
    *,
    font_size: int = 13,
) -> None:
    """Pack entity names as compact links that open their GM Table panels."""
    found = False
    for entity_type, raw_name in entries:
        name = str(raw_name or "").strip()
        if not name:
            continue
        found = True
        link = ctk.CTkButton(
            parent,
            text=name,
            height=22,
            border_width=0,
            corner_radius=0,
            fg_color="transparent",
            hover_color="#31415a",
            text_color=BOARD_TEXT,
            font=ctk.CTkFont(size=font_size, weight="bold", underline=True),
            command=lambda kind=entity_type, value=name: (
                callback(kind, value) if callable(callback) else None
            ),
        )
        link.pack(fill="x", padx=5, pady=0)
        link.configure(cursor="hand2")
    if not found:
        ctk.CTkLabel(
            parent,
            text="—",
            text_color=BOARD_TEXT,
            font=ctk.CTkFont(size=font_size),
        ).pack(fill="x", padx=5, pady=(0, 5))


def bind_full_width_wrap(label: ctk.CTkLabel, *, padding: int = 14) -> None:
    """Keep a label's wrapping width synchronized with its scene card."""

    def update_wrap(event) -> None:
        label.configure(wraplength=max(120, event.width - padding))

    label.bind("<Configure>", update_wrap, add="+")
