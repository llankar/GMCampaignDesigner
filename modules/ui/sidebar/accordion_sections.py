"""Sidebar accordion widgets with badges, grouping, and keyboard support."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable
import customtkinter as ctk


@dataclass(slots=True)
class SidebarItemSpec:
    icon_key: str
    tooltip: str
    command: Callable
    group: str | None = None


@dataclass(slots=True)
class SidebarSectionSpec:
    title: str
    items: list[SidebarItemSpec] = field(default_factory=list)
    item_count: int = 0
    has_unresolved: bool = False
    has_critical: bool = False
    updated_recently: bool = False


class SidebarAccordion:
    """Build and manage interactive sidebar sections."""

    def __init__(self, parent, icons, create_icon_button: Callable, tokens: dict | None = None):
        self.parent = parent
        self.icons = icons
        self._create_icon_button = create_icon_button
        self.tokens = tokens or {}
        self._sections: list[dict] = []
        self._header_order: list[ctk.CTkButton] = []
        self._active_section = None

    def build(self, specs: list[SidebarSectionSpec], default_title: str | None = None) -> None:
        for child in self.parent.winfo_children():
            child.destroy()
        self._sections.clear()
        self._header_order.clear()
        self._active_section = None

        for spec in specs:
            meta = self._make_section(spec)
            self._sections.append(meta)

        if default_title:
            self.open_section(default_title)

    def open_section(self, title: str) -> None:
        for meta in self._sections:
            if meta["title"] == title:
                self._activate(meta)
                meta["expand"]()
                return

    def _make_section(self, spec: SidebarSectionSpec) -> dict:
        section = ctk.CTkFrame(self.parent, fg_color="transparent")
        section.pack(fill="x", pady=(2, 5))

        inactive_fg = self.tokens.get("sidebar_header_bg", "#262626")
        active_fg = self.tokens.get("button_fg", "#2E6CCF")
        active_border = self.tokens.get("accent_button_fg", "#57A5FF")

        header = ctk.CTkButton(
            section,
            text="",
            fg_color=inactive_fg,
            hover_color=inactive_fg,
            border_width=1,
            border_color=self.tokens.get("button_border", "#3C3C3C"),
            corner_radius=8,
            anchor="w",
            command=lambda: self._toggle(meta),
        )
        header.pack(fill="x")

        accent = ctk.CTkFrame(header, width=4, corner_radius=2, fg_color="transparent")
        accent.pack(side="left", fill="y", padx=(0, 8), pady=2)

        title = ctk.CTkLabel(header, text=spec.title, anchor="w", font=("Segoe UI", 13, "bold"))
        title.pack(side="left", padx=(0, 8), pady=7)

        badges = ctk.CTkFrame(header, fg_color="transparent")
        badges.pack(side="right", padx=(6, 8), pady=4)

        count_text = str(spec.item_count if spec.item_count else len(spec.items))
        count_badge = ctk.CTkLabel(
            badges,
            text=count_text,
            width=24,
            corner_radius=10,
            fg_color=self.tokens.get("button_border", "#3C3C3C"),
            text_color=self.tokens.get("text", "#ECECEC"),
            font=("Segoe UI", 11, "bold"),
        )
        count_badge.pack(side="right", padx=(4, 0))

        if spec.has_unresolved or spec.has_critical:
            severity_color = "#E15241" if spec.has_critical else "#D9A441"
            severity_text = "!" if spec.has_critical else "?"
            severity_badge = ctk.CTkLabel(
                badges,
                text=severity_text,
                width=20,
                corner_radius=10,
                fg_color=severity_color,
                text_color="#FFFFFF",
                font=("Segoe UI", 11, "bold"),
            )
            severity_badge.pack(side="right", padx=(4, 0))

        if spec.updated_recently:
            updated_dot = ctk.CTkLabel(badges, text="•", text_color="#42D77D", font=("Segoe UI", 16, "bold"))
            updated_dot.pack(side="right", padx=(2, 0))

        body = ctk.CTkFrame(section, fg_color="transparent")
        self._build_body(body, spec.items)

        state = {"open": False}

        def expand():
            if state["open"]:
                return
            state["open"] = True
            body.pack(fill="x", padx=2, pady=(2, 2))

        def collapse():
            if not state["open"]:
                return
            state["open"] = False
            body.pack_forget()

        meta = {
            "sec": section,
            "title": spec.title,
            "header": header,
            "state": state,
            "expand": expand,
            "collapse": collapse,
            "accent": accent,
            "active_fg": active_fg,
            "active_border": active_border,
            "inactive_fg": inactive_fg,
        }

        header.configure(command=lambda m=meta: self._toggle(m))
        header.bind("<Up>", lambda e, m=meta: self._focus_adjacent(m, -1))
        header.bind("<Down>", lambda e, m=meta: self._focus_adjacent(m, +1))
        header.bind("<Return>", lambda e, m=meta: self._toggle(m))
        header.bind("<space>", lambda e, m=meta: self._toggle(m))
        header.bind("<FocusIn>", lambda e, h=header: h.configure(border_width=2))
        header.bind("<FocusOut>", lambda e, h=header: h.configure(border_width=1))
        self._header_order.append(header)
        return meta

    def _build_body(self, body, items: list[SidebarItemSpec]) -> None:
        groups: dict[str, list[SidebarItemSpec]] = {}
        for item in items:
            groups.setdefault(item.group or "", []).append(item)

        for group_name, group_items in groups.items():
            group_body = body
            if group_name:
                wrapper = ctk.CTkFrame(body, fg_color="transparent")
                wrapper.pack(fill="x", pady=(2, 4))
                expanded = {"open": True}
                group_body = ctk.CTkFrame(wrapper, fg_color="transparent")
                group_header = ctk.CTkButton(
                    wrapper,
                    text=f"{group_name} ▾",
                    height=24,
                    anchor="w",
                    fg_color="transparent",
                    hover_color=self.tokens.get("button_hover", "#2A2A2A"),
                    command=lambda gb=group_body, ex=expanded, gh=None: None,
                )
                group_header.pack(fill="x", padx=(2, 0), pady=(0, 2))

                def toggle_group(gb=group_body, ex=expanded, gh=group_header, name=group_name):
                    if ex["open"]:
                        gb.pack_forget()
                        gh.configure(text=f"{name} ▸")
                    else:
                        gb.pack(fill="x")
                        gh.configure(text=f"{name} ▾")
                    ex["open"] = not ex["open"]

                group_header.configure(command=toggle_group)
                group_body.pack(fill="x")

            cols = 2
            for cidx in range(cols):
                group_body.grid_columnconfigure(cidx, weight=1)
            for idx, item in enumerate(group_items):
                row, col = divmod(idx, cols)
                icon = self.icons.get(item.icon_key)
                btn = self._create_icon_button(group_body, icon, item.tooltip, item.command)
                btn.grid(row=row, column=col, padx=2, pady=2, sticky="ew")

    def _toggle(self, target_meta: dict) -> None:
        if target_meta["state"]["open"]:
            target_meta["collapse"]()
            if self._active_section is target_meta:
                self._style_section(target_meta, active=False)
                self._active_section = None
            return

        for meta in self._sections:
            if meta is target_meta:
                continue
            meta["collapse"]()
            self._style_section(meta, active=False)
        target_meta["expand"]()
        self._activate(target_meta)

    def _activate(self, meta: dict) -> None:
        self._active_section = meta
        self._style_section(meta, active=True)

    def _style_section(self, meta: dict, active: bool) -> None:
        if active:
            meta["header"].configure(
                fg_color=meta["active_fg"],
                hover_color=meta["active_fg"],
                border_color=meta["active_border"],
            )
            meta["accent"].configure(fg_color=meta["active_border"])
        else:
            meta["header"].configure(
                fg_color=meta["inactive_fg"],
                hover_color=meta["inactive_fg"],
                border_color=self.tokens.get("button_border", "#3C3C3C"),
            )
            meta["accent"].configure(fg_color="transparent")

    def _focus_adjacent(self, meta: dict, offset: int):
        try:
            current_idx = self._header_order.index(meta["header"])
        except ValueError:
            return
        target = self._header_order[(current_idx + offset) % len(self._header_order)]
        target.focus_set()
