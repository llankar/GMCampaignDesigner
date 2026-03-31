"""Utilities for scenario entity chips."""

from __future__ import annotations

import customtkinter as ctk


ENTITY_BASE_TINTS = {
    "NPCs": "#60A5FA",
    "Villains": "#F43F5E",
    "Creatures": "#22C55E",
    "Places": "#F59E0B",
}


def normalize_entity_payload(entity) -> dict:
    """Normalize entity payload."""
    if isinstance(entity, dict):
        name = str(
            entity.get("name")
            or entity.get("display_name")
            or entity.get("title")
            or ""
        ).strip()
        role = str(entity.get("role") or entity.get("short_role") or "").strip()
        avatar = entity.get("avatar") or entity.get("portrait") or entity.get("image")
    else:
        name = str(entity or "").strip()
        role = ""
        avatar = None
    return {"name": name, "role": role, "avatar": avatar}


def create_entity_chip(
    parent,
    *,
    group_label: str,
    entity_payload: dict,
    palette: dict,
    open_entity_callback=None,
):
    """Create entity chip."""
    chip_style = _resolve_chip_style(group_label, palette)
    entity_name = entity_payload["name"]
    entity_role = entity_payload["role"]
    avatar_data = entity_payload["avatar"]
    importance_level = str(entity_payload.get("importance") or "").strip()

    chip = ctk.CTkFrame(
        parent,
        fg_color=chip_style["fg"],
        border_width=1,
        border_color=chip_style["border"],
        corner_radius=999,
    )
    chip.configure(cursor="hand2" if callable(open_entity_callback) else "arrow")

    row = ctk.CTkFrame(chip, fg_color="transparent")
    row.pack(padx=(6, 10), pady=5)

    avatar_shell = ctk.CTkFrame(
        row,
        width=24,
        height=24,
        corner_radius=999,
        fg_color=chip_style["avatar_bg"],
        border_width=1,
        border_color=chip_style["avatar_border"],
    )
    avatar_shell.pack(side="left")
    avatar_shell.pack_propagate(False)

    initials = _entity_initials(entity_name)
    if avatar_data is not None:
        avatar_label = ctk.CTkLabel(avatar_shell, text="", image=avatar_data)
        avatar_label.image = avatar_data
    else:
        avatar_label = ctk.CTkLabel(
            avatar_shell,
            text=initials,
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color=chip_style["avatar_text"],
        )
    avatar_label.pack(expand=True)

    text_col = ctk.CTkFrame(row, fg_color="transparent")
    text_col.pack(side="left", padx=(8, 0))

    badge_label = None
    if importance_level:
        badge_label = ctk.CTkLabel(
            row,
            text=importance_level,
            font=ctk.CTkFont(size=9, weight="bold"),
            text_color=palette["muted_text"],
            fg_color=palette["pill_bg"],
            corner_radius=999,
            padx=7,
            pady=1,
        )
        badge_label.pack(side="right", padx=(10, 0), pady=(2, 0), anchor="n")

    name_label = ctk.CTkLabel(
        text_col,
        text=entity_name,
        font=ctk.CTkFont(size=12, weight="bold"),
        text_color=palette["text"],
    )
    name_label.pack(anchor="w")

    role_label = None
    if entity_role:
        role_label = ctk.CTkLabel(
            text_col,
            text=entity_role,
            font=ctk.CTkFont(size=10),
            text_color=palette["muted_text"],
        )
        role_label.pack(anchor="w", pady=(-1, 0))

    if callable(open_entity_callback):
        # Handle the branch where callable(open_entity_callback).
        _apply_interaction_state(
            chip,
            hover_fg=chip_style["hover_fg"],
            hover_border=chip_style["hover_border"],
            default_fg=chip_style["fg"],
            default_border=chip_style["border"],
            open_entity_callback=open_entity_callback,
            group_label=group_label,
            entity_name=entity_name,
        )
        for widget in (row, avatar_shell, avatar_label, text_col, name_label, role_label, badge_label):
            # Process each widget while updating entity chip.
            if widget is None:
                continue
            widget.configure(cursor="hand2")

    return chip


def _apply_interaction_state(
    chip,
    *,
    hover_fg,
    hover_border,
    default_fg,
    default_border,
    open_entity_callback,
    group_label,
    entity_name,
):
    """Apply interaction state."""
    def _on_enter(_event=None):
        """Handle enter."""
        chip.configure(fg_color=hover_fg, border_color=hover_border)

    def _on_leave(_event=None):
        """Handle leave."""
        chip.configure(fg_color=default_fg, border_color=default_border)

    def _open_entity(_event=None):
        """Open entity."""
        open_entity_callback(group_label, entity_name)

    _bind_to_tree(chip, "<Enter>", _on_enter)
    _bind_to_tree(chip, "<Leave>", _on_leave)
    _bind_to_tree(chip, "<Button-1>", _open_entity)


def _bind_to_tree(root, sequence, callback):
    """Bind to tree."""
    root.bind(sequence, callback, add="+")
    for child in root.winfo_children():
        _bind_to_tree(child, sequence, callback)


def _resolve_chip_style(group_label: str, palette: dict) -> dict:
    """Resolve chip style."""
    base_tint = ENTITY_BASE_TINTS.get(group_label, palette["accent"])
    return {
        "fg": _mix_hex(palette["surface_soft"], base_tint, 0.18),
        "border": _mix_hex(palette["border"], base_tint, 0.36),
        "hover_fg": _mix_hex(palette["surface_soft"], base_tint, 0.26),
        "hover_border": _mix_hex(base_tint, "#FFFFFF", 0.28),
        "avatar_bg": _mix_hex(base_tint, palette["surface"], 0.32),
        "avatar_border": _mix_hex(base_tint, palette["border"], 0.48),
        "avatar_text": palette["text"],
    }


def _entity_initials(value: str) -> str:
    """Internal helper for entity initials."""
    tokens = [token for token in value.split() if token]
    if not tokens:
        return "?"
    if len(tokens) == 1:
        return tokens[0][:2].upper()
    return f"{tokens[0][0]}{tokens[1][0]}".upper()


def _mix_hex(primary: str, secondary: str, amount: float) -> str:
    """Internal helper for mix hex."""
    primary = (primary or "").lstrip("#")
    secondary = (secondary or "").lstrip("#")
    if len(primary) != 6 or len(secondary) != 6:
        return f"#{primary if len(primary) == 6 else secondary}"
    ratio = max(0.0, min(1.0, float(amount)))
    red = int(int(primary[0:2], 16) * (1.0 - ratio) + int(secondary[0:2], 16) * ratio)
    green = int(int(primary[2:4], 16) * (1.0 - ratio) + int(secondary[2:4], 16) * ratio)
    blue = int(int(primary[4:6], 16) * (1.0 - ratio) + int(secondary[4:6], 16) * ratio)
    return f"#{red:02X}{green:02X}{blue:02X}"
