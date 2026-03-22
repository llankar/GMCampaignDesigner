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


class ScenarioSelectorStrip(_CanvasSelector):
    """Compact linear selector for the scenarios of the currently focused arc."""

    def __init__(
        self,
        parent,
        *,
        scenarios: Sequence[CampaignGraphScenario],
        selected_index: int,
        on_select: Callable[[int], None]
    ):
        self._scenarios = list(scenarios)
        self._selected_index = selected_index
        self._on_select = on_select
        super().__init__(parent, height=122, bg_color="#0d1728")

    def _render(self, *_args, **_kwargs) -> None:
        canvas = getattr(self, "canvas", None)
        if canvas is None or not canvas.winfo_exists():
            return

        canvas.delete("all")
        width = max(canvas.winfo_width(), 360)
        height = max(canvas.winfo_height(), 122)
        canvas.create_rectangle(0, 0, width, height, fill=self._bg_color, outline="")
        canvas.create_line(50, height / 2, width - 50, height / 2, fill="#28415f", width=3, smooth=True)

        count = max(len(self._scenarios), 1)
        step = max((width - 100) / count, 58)
        for index, scenario in enumerate(self._scenarios):
            x = 50 + step * index + step / 2
            y = height / 2
            selected = index == self._selected_index
            ring = "#8b5cf6" if selected else "#1e3a5f"
            fill = "#1b3150" if selected else "#142740"
            text_color = "#f8fbff" if selected else DASHBOARD_THEME.text_secondary
            dot_tag = f"scenario-dot:{index}"
            label_tag = f"scenario-label:{index}"

            canvas.create_oval(x - 24, y - 24, x + 24, y + 24, outline=ring, width=3, tags=(dot_tag,))
            canvas.create_oval(x - 18, y - 18, x + 18, y + 18, fill=fill, outline="#66c0ff", width=2, tags=(dot_tag,))
            canvas.create_text(x, y, text=str(index + 1), fill="#e5ecff", font=("Segoe UI", 11, "bold"), tags=(dot_tag,))
            canvas.create_text(
                x,
                y + 33,
                text=_truncate(scenario.title, 22),
                fill=text_color,
                font=("Segoe UI", 10, "bold"),
                width=max(step - 8, 50),
                justify="center",
                tags=(label_tag,),
            )
            canvas.tag_bind(dot_tag, "<Button-1>", lambda _e, idx=index: self._on_select(idx))
            canvas.tag_bind(label_tag, "<Button-1>", lambda _e, idx=index: self._on_select(idx))
            for tag in (dot_tag, label_tag):
                canvas.tag_bind(tag, "<Enter>", lambda _e: canvas.configure(cursor="hand2"))
                canvas.tag_bind(tag, "<Leave>", lambda _e: canvas.configure(cursor=""))


def _truncate(value: str, limit: int) -> str:
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return text[: max(limit - 1, 0)].rstrip() + "…"
