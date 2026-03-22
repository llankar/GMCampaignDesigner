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
        super().__init__(parent, height=156, bg_color="#091423")

    def _render(self, *_args, **_kwargs) -> None:
        canvas = getattr(self, "canvas", None)
        if canvas is None or not canvas.winfo_exists():
            return

        canvas.delete("all")
        width = max(canvas.winfo_width(), 420)
        height = max(canvas.winfo_height(), 156)
        canvas.create_rectangle(0, 0, width, height, fill=self._bg_color, outline="")

        count = max(len(self._arcs), 1)
        margin = 18
        gap = 12
        card_width = max(min((width - (margin * 2) - (gap * (count - 1))) / count, 240), 132)
        total_width = card_width * count + gap * max(count - 1, 0)
        start_x = max((width - total_width) / 2, margin)

        for index, arc in enumerate(self._arcs):
            x1 = start_x + index * (card_width + gap)
            x2 = x1 + card_width
            y1 = 18
            y2 = height - 18
            selected = index == self._selected_index
            tag = f"arc:{index}"
            fill = "#173454" if selected else "#0f1e32"
            outline = "#66c0ff" if selected else "#22395d"
            glow = "#264d78" if selected else "#13253d"
            title_color = "#f8fbff" if selected else DASHBOARD_THEME.text_primary
            meta_color = "#d6e9ff" if selected else DASHBOARD_THEME.text_secondary

            canvas.create_rectangle(x1 + 4, y1 + 6, x2 + 4, y2 + 6, fill="#07111d", outline="")
            canvas.create_rectangle(x1, y1, x2, y2, fill=fill, outline=outline, width=2, tags=(tag,))
            canvas.create_rectangle(x1, y1, x2, y1 + 8, fill=glow, outline="", tags=(tag,))

            canvas.create_text(
                x1 + 14,
                y1 + 24,
                text=f"ARC {index + 1}",
                fill="#8fb0dd",
                anchor="w",
                font=("Segoe UI", 10, "bold"),
                tags=(tag,),
            )
            canvas.create_text(
                x1 + 14,
                y1 + 48,
                text=_truncate(arc.name, 26),
                fill=title_color,
                anchor="w",
                width=max(card_width - 28, 40),
                font=("Segoe UI", 13, "bold"),
                tags=(tag,),
            )
            canvas.create_text(
                x1 + 14,
                y1 + 82,
                text=_truncate(arc.summary or arc.objective or "No arc pitch yet.", 54),
                fill=meta_color,
                anchor="nw",
                width=max(card_width - 28, 40),
                font=("Segoe UI", 9),
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


class ScenarioSelectorStrip(_CanvasSelector):
    """Cinematic rail selector for scenarios of the currently focused arc."""

    def __init__(
        self,
        parent,
        *,
        scenarios: Sequence[CampaignGraphScenario],
        selected_index: int,
        on_select: Callable[[int], None],
    ):
        self._scenarios = list(scenarios)
        self._selected_index = selected_index
        self._on_select = on_select
        super().__init__(parent, height=148, bg_color="#091423")

    def _render(self, *_args, **_kwargs) -> None:
        canvas = getattr(self, "canvas", None)
        if canvas is None or not canvas.winfo_exists():
            return

        canvas.delete("all")
        width = max(canvas.winfo_width(), 360)
        height = max(canvas.winfo_height(), 148)
        canvas.create_rectangle(0, 0, width, height, fill=self._bg_color, outline="")
        rail_y = height / 2 - 10
        canvas.create_line(54, rail_y, width - 54, rail_y, fill="#223b5c", width=4, smooth=True)

        count = max(len(self._scenarios), 1)
        step = max((width - 108) / count, 64)
        for index, scenario in enumerate(self._scenarios):
            x = 54 + step * index + step / 2
            y = rail_y
            selected = index == self._selected_index
            ring = "#8b5cf6" if selected else "#1e3a5f"
            halo = "#4c1d95" if selected else "#0b1626"
            fill = "#1b3150" if selected else "#122339"
            text_color = "#f8fbff" if selected else DASHBOARD_THEME.text_secondary
            dot_tag = f"scenario-dot:{index}"
            label_tag = f"scenario-label:{index}"
            shared_tags = (dot_tag, label_tag)

            canvas.create_oval(x - 28, y - 28, x + 28, y + 28, fill=halo, outline="", tags=shared_tags)
            canvas.create_oval(x - 24, y - 24, x + 24, y + 24, outline=ring, width=3, tags=shared_tags)
            canvas.create_oval(x - 18, y - 18, x + 18, y + 18, fill=fill, outline="#66c0ff", width=2, tags=shared_tags)
            canvas.create_text(x, y, text=str(index + 1), fill="#e5ecff", font=("Segoe UI", 11, "bold"), tags=shared_tags)
            canvas.create_text(
                x,
                y + 38,
                text=_truncate(scenario.title, 24),
                fill=text_color,
                font=("Segoe UI", 10, "bold"),
                width=max(step - 12, 56),
                justify="center",
                tags=shared_tags,
            )
            canvas.create_text(
                x,
                y + 62,
                text=_truncate(scenario.summary or f"{len(scenario.entity_links)} entity links", 34),
                fill="#8aa4c7",
                font=("Segoe UI", 8),
                width=max(step - 8, 58),
                justify="center",
                tags=shared_tags,
            )
            for tag in shared_tags:
                canvas.tag_bind(tag, "<Button-1>", lambda _e, idx=index: self._on_select(idx))
                canvas.tag_bind(tag, "<Enter>", lambda _e: canvas.configure(cursor="hand2"))
                canvas.tag_bind(tag, "<Leave>", lambda _e: canvas.configure(cursor=""))


def _truncate(value: str, limit: int) -> str:
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return text[: max(limit - 1, 0)].rstrip() + "…"
