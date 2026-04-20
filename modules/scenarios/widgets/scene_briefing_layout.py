"""Scene briefing layout widgets used by GM scene cards."""

from __future__ import annotations

import customtkinter as ctk


def _normalize_lines(values) -> list[str]:
    """Return cleaned non-empty lines."""
    items: list[str] = []
    for value in values or []:
        text = " ".join(str(value or "").split()).strip()
        if text:
            items.append(text)
    return items


def _create_column(parent, *, title: str, lines: list[str], palette: dict, empty_text: str = "—") -> None:
    """Create one briefing column."""
    col = ctk.CTkFrame(
        parent,
        fg_color="transparent",
        border_width=1,
        border_color=palette["muted_border"],
        corner_radius=12,
    )
    col.pack(side="left", fill="both", expand=True, padx=4, pady=0)

    ctk.CTkLabel(
        col,
        text=title.upper(),
        anchor="w",
        text_color=palette["muted_text"],
        font=ctk.CTkFont(size=10, weight="bold"),
    ).pack(fill="x", padx=10, pady=(9, 6))

    body = ctk.CTkFrame(col, fg_color="transparent")
    body.pack(fill="both", expand=True, padx=10, pady=(0, 10))

    rendered = _normalize_lines(lines)[:6]
    if not rendered:
        ctk.CTkLabel(
            body,
            text=empty_text,
            anchor="w",
            justify="left",
            text_color=palette["muted_text"],
            font=ctk.CTkFont(size=12, slant="italic"),
        ).pack(fill="x", pady=(0, 5))
        return

    labels = []
    for line in rendered:
        label = ctk.CTkLabel(
            body,
            text=f"• {line}",
            anchor="w",
            justify="left",
            text_color=palette["text"],
            font=ctk.CTkFont(size=12),
            wraplength=0,
        )
        label.pack(fill="x", pady=(0, 5))
        labels.append(label)

    def _refresh_wrap(_event=None):
        """Refresh column wrap lengths."""
        wrap_px = max(180, int(body.winfo_width()) - 8)
        for current in labels:
            current.configure(wraplength=wrap_px)

    body.bind("<Configure>", _refresh_wrap, add="+")
    _refresh_wrap()


def create_scene_briefing_layout(
    parent,
    *,
    npc_names: list[str],
    place_names: list[str],
    clue_lines: list[str],
    event_lines: list[str],
    palette: dict,
) -> ctk.CTkFrame:
    """Create a 4-column scene intel strip inspired by the design mockup."""
    board = ctk.CTkFrame(
        parent,
        fg_color=palette["surface_card"],
        corner_radius=14,
        border_width=1,
        border_color=palette["muted_border"],
    )
    board.pack(fill="x", padx=12, pady=(4, 10))

    columns = ctk.CTkFrame(board, fg_color="transparent")
    columns.pack(fill="x", padx=8, pady=8)

    _create_column(columns, title="NPCs in scene", lines=npc_names, palette=palette)
    _create_column(columns, title="Places", lines=place_names, palette=palette)
    _create_column(columns, title="Clues", lines=clue_lines, palette=palette)
    _create_column(columns, title="Events & triggers", lines=event_lines, palette=palette)
    return board
