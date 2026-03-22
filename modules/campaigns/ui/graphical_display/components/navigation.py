from __future__ import annotations

import tkinter as tk
from typing import Callable, Sequence

import customtkinter as ctk

from modules.scenarios.gm_screen.dashboard.styles.dashboard_theme import DASHBOARD_THEME
from ..data import CampaignGraphArc, CampaignGraphScenario


class _CanvasSelector(ctk.CTkFrame):
    def __init__(self, parent, *, height: int, bg_color: str):
        super().__init__(parent, fg_color="transparent")
        self._bg_color = bg_color
        self.canvas = tk.Canvas(
            self,
            height=height,
            bg=bg_color,
            highlightthickness=0,
            bd=0,
        )
        self.canvas.pack(fill="x", expand=True)
        self.canvas.bind("<Configure>", self._render)
        self.after_idle(self._render)

    def _render(self, *_args, **_kwargs) -> None:
        raise NotImplementedError


class ArcSelectorStrip(_CanvasSelector):
    """Graphical selector that previews every arc while keeping only one arc expanded."""

    def __init__(
        self,
        parent,
        *,
        arcs: Sequence[CampaignGraphArc],
        selected_index: int,
        on_select: Callable[[int], None],
    ):
        self._arcs = list(arcs)
        self._selected_index = selected_index
        self._on_select = on_select
        super().__init__(parent, height=124, bg_color="#0d1728")

    def _render(self, *_args, **_kwargs) -> None:
        canvas = getattr(self, "canvas", None)
        if canvas is None or not canvas.winfo_exists():
            return

        canvas.delete("all")
        width = max(canvas.winfo_width(), 420)
        height = max(canvas.winfo_height(), 124)
        canvas.create_rectangle(0, 0, width, height, fill=self._bg_color, outline="")

        count = max(len(self._arcs), 1)
        margin = 20
        gap = 12
        card_width = max(min((width - (margin * 2) - (gap * (count - 1))) / count, 220), 118)
        total_width = card_width * count + gap * max(count - 1, 0)
        start_x = max((width - total_width) / 2, margin)

        for index, arc in enumerate(self._arcs):
            x1 = start_x + index * (card_width + gap)
            x2 = x1 + card_width
            y1 = 18
            y2 = height - 18
            selected = index == self._selected_index
            tag = f"arc:{index}"
            fill = "#173454" if selected else "#101f34"
            outline = "#66c0ff" if selected else "#22395d"
            title_color = "#f8fbff" if selected else DASHBOARD_THEME.text_primary
            meta_color = "#d6e9ff" if selected else DASHBOARD_THEME.text_secondary

            canvas.create_rectangle(x1, y1, x2, y2, fill=fill, outline=outline, width=2, tags=(tag,))
            canvas.create_text(
                x1 + 14,
                y1 + 18,
                text=f"Arc {index + 1}",
                fill="#8fb0dd",
                anchor="w",
                font=("Segoe UI", 10, "bold"),
                tags=(tag,),
            )
            canvas.create_text(
                x1 + 14,
                y1 + 42,
                text=_truncate(arc.name, 24),
                fill=title_color,
                anchor="w",
                width=max(card_width - 28, 40),
                font=("Segoe UI", 12, "bold"),
                tags=(tag,),
            )
            canvas.create_text(
                x1 + 14,
                y2 - 18,
                text=f"{arc.status} • {len(arc.scenarios)} scenarios",
                fill=meta_color,
                anchor="sw",
                font=("Segoe UI", 9, "bold"),
                tags=(tag,),
            )
            canvas.tag_bind(tag, "<Button-1>", lambda _e, idx=index: self._on_select(idx))
            canvas.tag_bind(tag, "<Enter>", lambda _e: canvas.configure(cursor="hand2"))
            canvas.tag_bind(tag, "<Leave>", lambda _e: canvas.configure(cursor=""))


class ScenarioSelectorStrip(ctk.CTkFrame):
    """Horizontal mission-card selector for scenarios inside the active arc."""

    def __init__(
        self,
        parent,
        *,
        scenarios: Sequence[CampaignGraphScenario],
        selected_index: int,
        on_select: Callable[[int], None],
    ):
        super().__init__(parent, fg_color="#0d1728", corner_radius=18)
        self._scenarios = list(scenarios)
        self._selected_index = selected_index
        self._on_select = on_select

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.canvas = tk.Canvas(self, height=142, bg="#0d1728", highlightthickness=0, bd=0)
        self.canvas.grid(row=0, column=0, sticky="ew")
        self.scrollbar = ctk.CTkScrollbar(self, orientation="horizontal", command=self.canvas.xview)
        self.scrollbar.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 8))
        self.canvas.configure(xscrollcommand=self.scrollbar.set)

        self.inner = ctk.CTkFrame(self.canvas, fg_color="#0d1728")
        self.canvas_window = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.inner.bind("<Configure>", self._sync_scrollregion)
        self.canvas.bind("<Configure>", self._resize_window)
        self.after_idle(self._render)

    def _render(self) -> None:
        for child in self.inner.winfo_children():
            child.destroy()

        many_scenarios = len(self._scenarios) >= 7
        card_width = 180 if many_scenarios else 220
        for index, scenario in enumerate(self._scenarios):
            selected = index == self._selected_index
            card = ctk.CTkFrame(
                self.inner,
                fg_color="#183252" if selected else "#122038",
                corner_radius=18,
                border_width=2 if selected else 1,
                border_color="#66c0ff" if selected else "#243a5c",
                width=card_width,
                height=118,
            )
            card.grid(row=0, column=index, sticky="nsw", padx=(0, 10), pady=10)
            card.grid_propagate(False)
            card.grid_columnconfigure(0, weight=1)

            ctk.CTkLabel(
                card,
                text=f"MISSION {index + 1}",
                text_color="#8fb0dd",
                font=ctk.CTkFont(size=10, weight="bold"),
                anchor="w",
            ).grid(row=0, column=0, sticky="w", padx=14, pady=(12, 4))
            ctk.CTkLabel(
                card,
                text=_truncate(scenario.title, 28),
                text_color="#f8fbff" if selected else DASHBOARD_THEME.text_primary,
                font=ctk.CTkFont(size=14, weight="bold"),
                justify="left",
                anchor="w",
            ).grid(row=1, column=0, sticky="ew", padx=14)

            meta = ctk.CTkFrame(card, fg_color="transparent")
            meta.grid(row=2, column=0, sticky="w", padx=14, pady=(8, 6))
            first_type = scenario.primary_link_type or "No links"
            for meta_index, label in enumerate((f"{scenario.linked_entity_count} links", first_type, f"{scenario.scene_count or 0} scenes")):
                ctk.CTkLabel(
                    meta,
                    text=label,
                    fg_color="#10233a",
                    corner_radius=999,
                    padx=8,
                    pady=3,
                    text_color="#dceaff",
                    font=ctk.CTkFont(size=10, weight="bold"),
                ).grid(row=0, column=meta_index, padx=(0, 6))

            ctk.CTkButton(
                card,
                text="View",
                command=lambda idx=index: self._on_select(idx),
                fg_color=DASHBOARD_THEME.accent if selected else "#17263d",
                hover_color=DASHBOARD_THEME.accent_hover if selected else "#223a5f",
                height=28,
                width=92,
            ).grid(row=3, column=0, sticky="w", padx=14, pady=(0, 12))

        self.after_idle(self._sync_scrollregion)

    def _sync_scrollregion(self, _event=None) -> None:
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _resize_window(self, event) -> None:
        self.canvas.itemconfigure(self.canvas_window, height=event.height)


def _truncate(value: str, limit: int) -> str:
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return text[: max(limit - 1, 0)].rstrip() + "…"
