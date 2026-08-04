"""Reusable linked entity lists for the Scenario Board."""

from __future__ import annotations

from collections.abc import Callable, Iterable

import customtkinter as ctk

from modules.scenarios.gm_table.scenario_board.styles import ScenarioBoardPalette

OpenEntityCallback = Callable[[str, str], None]


def add_entity_links(
    parent,
    entries: Iterable[tuple[str, str]],
    callback: OpenEntityCallback | None,
    *,
    font_size: int = 13,
    palette: ScenarioBoardPalette,
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
            hover_color=palette.control_hover,
            text_color=(
                palette.villain_text if entity_type == "Villains" else palette.text
            ),
            font=ctk.CTkFont(size=font_size, underline=True),
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
            text_color=palette.text,
            font=ctk.CTkFont(size=font_size),
        ).pack(fill="x", padx=5, pady=(0, 5))


def bind_full_width_wrap(
    label: ctk.CTkLabel,
    *,
    padding: int = 14,
    initial_wraplength: int = 320,
) -> None:
    """Keep a label's wrapping width synchronized with its containing card.

    Listening to the label itself creates a feedback loop: changing ``wraplength``
    changes the label's requested size, which emits another ``<Configure>`` event.
    On content-heavy boards that loop can keep Tk's event queue busy indefinitely.
    The card width is the stable value we actually want, so listen to the parent and
    skip duplicate values instead.
    """

    parent = label.master
    last_wraplength: int | None = max(120, initial_wraplength)
    label.configure(wraplength=last_wraplength)

    def update_wrap(event) -> None:
        nonlocal last_wraplength
        wraplength = max(120, event.width - padding)
        if wraplength == last_wraplength:
            return
        last_wraplength = wraplength
        label.configure(wraplength=wraplength)

    parent.bind("<Configure>", update_wrap, add="+")
