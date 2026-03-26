from __future__ import annotations

import customtkinter as ctk

from modules.generic.editor.styles import get_editor_palette


def resolve_color(value):
    if isinstance(value, (list, tuple)):
        appearance = ctk.get_appearance_mode()
        index = 1 if appearance == "Dark" else 0
        if not value:
            return None
        if index >= len(value):
            index = len(value) - 1
        return value[index]
    return value


def get_detail_palette() -> dict:
    palette = dict(get_editor_palette())
    palette.update(
        {
            "surface_card": palette["surface_alt"],
            "surface_elevated": palette["surface_soft"],
            "surface_overlay": _mix_hex(palette["surface"], palette["accent"], 0.18),
            "hero_gradient": _mix_hex(palette["surface_alt"], palette["accent"], 0.34),
            "hero_glow": _mix_hex(palette["accent"], "#FFFFFF", 0.18),
            "hero_band": _mix_hex(palette["accent"], "#FFFFFF", 0.08),
            "link": _mix_hex(palette["accent"], "#7DD3FC", 0.28),
            "link_hover": _mix_hex(palette["accent_hover"], "#FFFFFF", 0.18),
            "pill_bg": _mix_hex(palette["surface_soft"], palette["accent"], 0.14),
            "pill_border": _mix_hex(palette["border"], palette["accent"], 0.32),
            "muted_border": _mix_hex(palette["border"], palette["surface_soft"], 0.35),
        }
    )
    return palette


def get_link_color() -> str:
    return get_detail_palette()["link"]


def get_textbox_style() -> dict:
    palette = get_detail_palette()
    return {
        "fg_color": palette["surface_elevated"],
        "border_width": 1,
        "border_color": palette["muted_border"],
        "text_color": palette["text"],
        "corner_radius": 14,
    }


def create_section_card(parent, title: str, subtitle: str | None = None, *, compact: bool = False):
    palette = get_detail_palette()
    outer = ctk.CTkFrame(
        parent,
        fg_color=palette["surface_card"],
        border_width=1,
        border_color=palette["muted_border"],
        corner_radius=18,
    )
    header = ctk.CTkFrame(outer, fg_color="transparent")
    header.pack(fill="x", padx=16, pady=(14, 6 if compact else 8))
    ctk.CTkLabel(
        header,
        text=title,
        font=ctk.CTkFont(size=16 if compact else 17, weight="bold"),
        text_color=palette["text"],
    ).pack(anchor="w")
    if subtitle:
        ctk.CTkLabel(
            header,
            text=subtitle,
            font=ctk.CTkFont(size=12),
            text_color=palette["muted_text"],
            wraplength=640,
            justify="left",
        ).pack(anchor="w", pady=(4, 0))
    body = ctk.CTkFrame(outer, fg_color="transparent")
    body.pack(fill="both", expand=True, padx=16, pady=(0, 16))
    return outer, body


def create_chip(parent, text: str, *, accent: bool = False):
    palette = get_detail_palette()
    chip = ctk.CTkFrame(
        parent,
        fg_color=palette["surface_overlay"] if accent else palette["pill_bg"],
        border_width=1,
        border_color=palette["pill_border"],
        corner_radius=999,
    )
    ctk.CTkLabel(
        chip,
        text=text,
        font=ctk.CTkFont(size=12, weight="bold" if accent else "normal"),
        text_color=palette["text"],
    ).pack(padx=12, pady=6)
    return chip


def create_hero_header(
    parent,
    *,
    title: str,
    category: str,
    summary: str | None = None,
    meta_items: list[str] | None = None,
    portrait_widget=None,
    portrait_builder=None,
    adaptive_wrap: bool = True,
):
    palette = get_detail_palette()
    hero = ctk.CTkFrame(
        parent,
        fg_color=palette["hero_gradient"],
        border_width=1,
        border_color=palette["pill_border"],
        corner_radius=28,
    )

    band = ctk.CTkFrame(hero, fg_color=palette["hero_band"], height=8, corner_radius=28)
    band.pack(fill="x", padx=18, pady=(0, 0))

    content = ctk.CTkFrame(hero, fg_color="transparent")
    content.pack(fill="both", expand=True, padx=26, pady=(14, 20))
    content.grid_columnconfigure(0, weight=7)
    content.grid_rowconfigure(0, weight=1)
    if portrait_widget is not None or portrait_builder is not None:
        content.grid_columnconfigure(1, weight=4, minsize=260)

    text_col = ctk.CTkFrame(content, fg_color="transparent")
    text_col.grid(row=0, column=0, sticky="nsew", padx=(0, 18))

    badge_row = ctk.CTkFrame(text_col, fg_color="transparent")
    badge_row.pack(fill="x")
    create_chip(badge_row, category.upper(), accent=True).pack(side="left")
    if meta_items:
        create_chip(badge_row, f"{len([item for item in meta_items if item])} signals").pack(side="left", padx=(8, 0))

    title_label = ctk.CTkLabel(
        text_col,
        text=title,
        font=ctk.CTkFont(size=28, weight="bold"),
        text_color=palette["text"],
        justify="left",
        wraplength=820,
    )
    title_label.pack(anchor="w", fill="x", pady=(12, 8))

    summary_label = None
    if summary:
        summary_label = ctk.CTkLabel(
            text_col,
            text=summary,
            font=ctk.CTkFont(size=13),
            text_color=palette["muted_text"],
            justify="left",
            wraplength=760,
        )
        summary_label.pack(anchor="w", fill="x")

    if meta_items:
        meta_flow = ctk.CTkFrame(text_col, fg_color="transparent")
        meta_flow.pack(fill="x", pady=(14, 0))
        for item in meta_items:
            if not item:
                continue
            create_chip(meta_flow, item).pack(side="left", padx=(0, 8), pady=(0, 8))

    if portrait_widget is not None or portrait_builder is not None:
        portrait_shell = ctk.CTkFrame(
            content,
            fg_color=palette["surface_overlay"],
            border_width=1,
            border_color=palette["pill_border"],
            corner_radius=24,
            width=300,
            height=260,
        )
        portrait_shell.grid(row=0, column=1, sticky="nsew")
        portrait_shell.grid_propagate(False)
        rendered_portrait = portrait_widget or (portrait_builder(portrait_shell) if portrait_builder is not None else None)
        if rendered_portrait is not None:
            rendered_portrait.pack(fill="both", expand=True, padx=12, pady=12)

    if adaptive_wrap:
        def _update_wrap(_event=None):
            try:
                text_width = int(text_col.winfo_width())
            except Exception:
                return
            if text_width <= 1:
                return
            title_wrap = max(320, text_width - 8)
            summary_wrap = max(320, text_width - 8)
            try:
                title_label.configure(wraplength=title_wrap)
            except Exception:
                pass
            if summary_label is not None:
                try:
                    summary_label.configure(wraplength=summary_wrap)
                except Exception:
                    pass

        text_col.bind("<Configure>", _update_wrap, add="+")
        hero.after_idle(_update_wrap)

    return hero


def _mix_hex(primary: str, secondary: str, amount: float) -> str:
    primary = primary.lstrip("#")
    secondary = secondary.lstrip("#")
    if len(primary) != 6 or len(secondary) != 6:
        return f"#{primary if len(primary) == 6 else secondary}"
    amount = max(0.0, min(1.0, amount))
    channels = []
    for idx in range(0, 6, 2):
        a = int(primary[idx:idx + 2], 16)
        b = int(secondary[idx:idx + 2], 16)
        mixed = round(a + (b - a) * amount)
        channels.append(f"{mixed:02x}")
    return f"#{''.join(channels)}"
