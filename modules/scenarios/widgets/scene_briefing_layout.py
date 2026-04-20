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


def _normalize_rows(values) -> list[dict]:
    """Return cleaned rows with optional avatar image."""
    rows: list[dict] = []
    for value in values or []:
        if isinstance(value, dict):
            line = " ".join(str(value.get("line") or value.get("text") or "").split()).strip()
            avatar = value.get("avatar")
        else:
            line = " ".join(str(value or "").split()).strip()
            avatar = None
        if line:
            rows.append({"line": line, "avatar": avatar})
    return rows


def _create_row(parent, *, line: str, palette: dict, icon: str = "•", emphasized: bool = False, avatar=None) -> ctk.CTkLabel:
    """Create one line row inside a scene briefing column."""
    row_shell = ctk.CTkFrame(parent, fg_color="transparent")
    row_shell.pack(fill="x", pady=(0, 6))

    if avatar is not None:
        avatar_label = ctk.CTkLabel(row_shell, text="", image=avatar)
        avatar_label.image = avatar
        avatar_label.pack(side="left", padx=(0, 8), pady=1)

    row = ctk.CTkLabel(
        row_shell,
        text=f"{icon}  {line}",
        anchor="w",
        justify="left",
        text_color=palette["text"] if emphasized else palette["muted_text"],
        font=ctk.CTkFont(size=12, weight="bold" if emphasized else "normal"),
        wraplength=0,
    )
    row.pack(side="left", fill="x", expand=True)
    return row


def _create_column(
    parent,
    *,
    title: str,
    lines: list[str],
    palette: dict,
    empty_text: str = "—",
    row_icon: str = "•",
    footer_text: str | None = None,
) -> None:
    """Create one briefing column."""
    col = ctk.CTkFrame(parent, fg_color="transparent")
    col.pack(side="left", fill="both", expand=True, padx=12, pady=0)

    ctk.CTkLabel(
        col,
        text=title.upper(),
        anchor="w",
        text_color=palette["muted_text"],
        font=ctk.CTkFont(size=10, weight="bold"),
    ).pack(fill="x", pady=(2, 10))

    body = ctk.CTkFrame(col, fg_color="transparent")
    body.pack(fill="both", expand=True)

    rendered = _normalize_rows(lines)[:6]
    labels = []

    if not rendered:
        labels.append(
            _create_row(
                body,
                line=empty_text,
                palette=palette,
                icon="",
            )
        )
    else:
        for index, item in enumerate(rendered):
            labels.append(
                _create_row(
                    body,
                    line=item["line"],
                    palette=palette,
                    icon=row_icon,
                    emphasized=index == 0,
                    avatar=item.get("avatar"),
                )
            )

    if footer_text:
        ctk.CTkLabel(
            col,
            text=footer_text,
            anchor="w",
            text_color=palette["accent"],
            font=ctk.CTkFont(size=11, weight="bold"),
            cursor="hand2",
        ).pack(fill="x", pady=(4, 0))

    def _refresh_wrap(_event=None):
        """Refresh column wrap lengths."""
        wrap_px = max(140, int(body.winfo_width()) - 8)
        for current in labels:
            current.configure(wraplength=wrap_px)

    body.bind("<Configure>", _refresh_wrap, add="+")
    _refresh_wrap()


def _add_vertical_separator(parent, palette: dict) -> None:
    """Add a thin separator between columns."""
    ctk.CTkFrame(parent, width=1, fg_color=palette["muted_border"]).pack(side="left", fill="y", pady=6)


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

    _create_column(
        columns,
        title="NPCs in scene",
        lines=npc_names,
        palette=palette,
        row_icon="👤",
        footer_text=f"View all {len(_normalize_rows(npc_names))} NPCs" if npc_names else None,
    )
    _add_vertical_separator(columns, palette)

    _create_column(
        columns,
        title="Places",
        lines=place_names,
        palette=palette,
        row_icon="📍",
        footer_text="View on map" if place_names else None,
    )
    _add_vertical_separator(columns, palette)

    _create_column(
        columns,
        title="Clues",
        lines=clue_lines,
        palette=palette,
        row_icon="☑",
        footer_text="Manage clues" if clue_lines else None,
    )
    _add_vertical_separator(columns, palette)

    _create_column(
        columns,
        title="Events & triggers",
        lines=event_lines,
        palette=palette,
        row_icon="⚙",
        footer_text=f"View all events ({len(_normalize_lines(event_lines))})" if event_lines else None,
    )
    return board
