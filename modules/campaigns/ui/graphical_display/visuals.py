from __future__ import annotations

import tkinter as tk
from typing import Callable

import customtkinter as ctk

from modules.scenarios.gm_screen.dashboard.styles.dashboard_theme import DASHBOARD_THEME
from .components.entity_constellation import EntityConstellation
from .data import CampaignGraphScenario


class ArcScenarioStrip(ctk.CTkFrame):
    """Compact linear graph for scenarios inside an arc."""

    def __init__(self, parent, *, scenarios: list[CampaignGraphScenario], on_open_scenario: Callable[[str], None]):
        super().__init__(parent, fg_color="transparent")
        self._scenarios = scenarios
        self._on_open_scenario = on_open_scenario

        height = 106
        self.canvas = tk.Canvas(
            self,
            height=height,
            bg=DASHBOARD_THEME.card_bg,
            highlightthickness=0,
            bd=0,
        )
        self.canvas.pack(fill="x", expand=True)
        self.canvas.bind("<Configure>", self._render)
        self.after_idle(self._render)

    def _render(self, *_args, **_kwargs) -> None:
        canvas = getattr(self, "canvas", None)
        if canvas is None or not canvas.winfo_exists():
            return

        canvas.delete("all")
        width = max(canvas.winfo_width(), 360)
        height = max(canvas.winfo_height(), 106)

        canvas.create_rectangle(0, 0, width, height, fill=DASHBOARD_THEME.card_bg, outline="")
        canvas.create_line(48, height / 2, width - 48, height / 2, fill="#28415f", width=3, smooth=True)

        count = max(len(self._scenarios), 1)
        step = (width - 96) / count
        for index, scenario in enumerate(self._scenarios):
            x = 48 + step * index + step / 2
            y = height / 2
            r = 18
            tag = f"scenario:{index}"
            canvas.create_oval(x - r - 6, y - r - 6, x + r + 6, y + r + 6, outline="#1e3a5f", width=2, tags=(tag,))
            canvas.create_oval(x - r, y - r, x + r, y + r, fill="#142740", outline="#66c0ff", width=2, tags=(tag,))
            canvas.create_text(x, y, text=str(index + 1), fill="#e5ecff", font=("Segoe UI", 11, "bold"), tags=(tag,))
            canvas.create_text(
                x,
                y + 32,
                text=_truncate(scenario.title, 18),
                fill=DASHBOARD_THEME.text_secondary,
                font=("Segoe UI", 10, "bold"),
                width=step - 10,
                justify="center",
                tags=(tag,),
            )
            canvas.tag_bind(tag, "<Button-1>", lambda _e, n=scenario.title: self._on_open_scenario(n))
            canvas.tag_bind(tag, "<Enter>", lambda _e: canvas.configure(cursor="hand2"))
            canvas.tag_bind(tag, "<Leave>", lambda _e: canvas.configure(cursor=""))


def _truncate(value: str, limit: int) -> str:
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return text[: max(limit - 1, 0)].rstrip() + "…"


__all__ = ["ArcScenarioStrip", "EntityConstellation"]
