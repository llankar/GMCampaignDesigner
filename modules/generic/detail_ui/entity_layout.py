from __future__ import annotations

import math
from typing import Iterable

import customtkinter as ctk

from .theme import create_chip, create_section_card, get_detail_palette


LAYOUT_BREAKPOINT = 1180


def create_detail_split_layout(parent, *, sidebar_width: int = 380):
    """Build a 16:9-friendly content split with a main stage and a utility rail."""

    palette = get_detail_palette()
    shell = ctk.CTkFrame(parent, fg_color="transparent")
    shell.grid_columnconfigure(0, weight=5)
    shell.grid_columnconfigure(1, weight=3, minsize=sidebar_width)
    shell.grid_rowconfigure(0, weight=1)

    main_column = ctk.CTkFrame(shell, fg_color="transparent")
    main_column.grid(row=0, column=0, sticky="nsew", padx=(0, 14))

    side_column = ctk.CTkFrame(
        shell,
        fg_color=palette["surface_card"],
        border_width=1,
        border_color=palette["muted_border"],
        corner_radius=24,
    )
    side_column.grid(row=0, column=1, sticky="nsew")

    side_inner = ctk.CTkFrame(side_column, fg_color="transparent")
    side_inner.pack(fill="both", expand=True, padx=18, pady=18)

    def _stack_layout():
        if not shell.winfo_exists():
            return
        try:
            width = shell.winfo_width()
        except Exception:
            width = 0
        if width and width < LAYOUT_BREAKPOINT:
            main_column.grid_configure(row=1, column=0, columnspan=2, padx=0, pady=(0, 14))
            side_column.grid_configure(row=0, column=0, columnspan=2, sticky="ew")
        else:
            main_column.grid_configure(row=0, column=0, columnspan=1, padx=(0, 14), pady=0)
            side_column.grid_configure(row=0, column=1, columnspan=1, sticky="nsew")

    shell.bind("<Configure>", lambda _event: _stack_layout(), add="+")
    shell.after(30, _stack_layout)
    return shell, main_column, side_inner


def create_spotlight_panel(
    parent,
    *,
    title: str,
    subtitle: str | None = None,
    portrait_widget=None,
    portrait_builder=None,
    fallback_text: str = "No portrait linked yet.",
    accent_lines: Iterable[str] | None = None,
):
    palette = get_detail_palette()
    card = ctk.CTkFrame(
        parent,
        fg_color=palette["surface_overlay"],
        border_width=1,
        border_color=palette["pill_border"],
        corner_radius=22,
    )
    card.pack(fill="x", pady=(0, 14))

    header = ctk.CTkFrame(card, fg_color="transparent")
    header.pack(fill="x", padx=18, pady=(18, 10))
    create_chip(header, "SPOTLIGHT", accent=True).pack(anchor="w")
    ctk.CTkLabel(
        header,
        text=title,
        font=ctk.CTkFont(size=18, weight="bold"),
        text_color=palette["text"],
        justify="left",
        wraplength=280,
    ).pack(anchor="w", pady=(12, 4))
    if subtitle:
        ctk.CTkLabel(
            header,
            text=subtitle,
            font=ctk.CTkFont(size=12),
            text_color=palette["muted_text"],
            justify="left",
            wraplength=280,
        ).pack(anchor="w")

    portrait_shell = ctk.CTkFrame(
        card,
        fg_color=palette["surface_card"],
        border_width=1,
        border_color=palette["muted_border"],
        corner_radius=20,
        height=430,
    )
    portrait_shell.pack(fill="x", padx=18, pady=(0, 16))
    portrait_shell.pack_propagate(False)

    rendered_portrait = portrait_widget or (portrait_builder(portrait_shell) if portrait_builder is not None else None)
    if rendered_portrait is not None:
        rendered_portrait.pack(fill="both", expand=True, padx=10, pady=10)
    else:
        empty = ctk.CTkFrame(portrait_shell, fg_color="transparent")
        empty.pack(fill="both", expand=True, padx=18, pady=18)
        ctk.CTkLabel(
            empty,
            text="✦",
            font=ctk.CTkFont(size=44, weight="bold"),
            text_color=palette["accent"],
        ).pack(pady=(40, 12))
        ctk.CTkLabel(
            empty,
            text=fallback_text,
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=palette["text"],
            wraplength=240,
            justify="center",
        ).pack(pady=(0, 8))
        ctk.CTkLabel(
            empty,
            text="Add art to turn this panel into a full-height character spotlight.",
            font=ctk.CTkFont(size=12),
            text_color=palette["muted_text"],
            wraplength=240,
            justify="center",
        ).pack()

    if accent_lines:
        footer = ctk.CTkFrame(card, fg_color="transparent")
        footer.pack(fill="x", padx=18, pady=(0, 18))
        for line in accent_lines:
            if not str(line).strip():
                continue
            ctk.CTkLabel(
                footer,
                text=f"• {line}",
                font=ctk.CTkFont(size=12),
                text_color=palette["muted_text"],
                justify="left",
                wraplength=280,
            ).pack(anchor="w", pady=(0, 4))

    return card


def create_highlight_card(parent, title: str, lines: Iterable[str], *, empty_state: str = "No highlights yet."):
    card, body = create_section_card(parent, title, "Quick-read beats to anchor the scene.", compact=True)
    card.pack(fill="x", pady=(0, 14))
    palette = get_detail_palette()
    added = False
    for line in lines:
        text = str(line or "").strip()
        if not text:
            continue
        added = True
        row = ctk.CTkFrame(body, fg_color="transparent")
        row.pack(fill="x", pady=(0, 8))
        dot = ctk.CTkFrame(row, width=10, height=10, corner_radius=999, fg_color=palette["accent"])
        dot.pack(side="left", padx=(0, 10), pady=(5, 0))
        dot.pack_propagate(False)
        ctk.CTkLabel(
            row,
            text=text,
            font=ctk.CTkFont(size=12),
            text_color=palette["text"],
            justify="left",
            wraplength=260,
        ).pack(side="left", fill="x", expand=True)
    if not added:
        ctk.CTkLabel(
            body,
            text=empty_state,
            font=ctk.CTkFont(size=12),
            text_color=palette["muted_text"],
            justify="left",
            wraplength=260,
        ).pack(anchor="w")
    return card


def estimate_field_height(field_type: str, value) -> int:
    if field_type == "longtext":
        text = str(value or "")
        return 3 + math.ceil(len(text) / 320)
    if field_type == "list":
        return max(2, len(value or []))
    return 2
