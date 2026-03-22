from __future__ import annotations

import math
import tkinter as tk
from collections import defaultdict
from typing import Callable, Iterable

import customtkinter as ctk

from modules.scenarios.gm_screen.dashboard.styles.dashboard_theme import DASHBOARD_THEME
from .data import CampaignGraphScenario, ScenarioEntityLink


_ENTITY_COLORS = {
    "NPCs": "#f59e0b",
    "PCs": "#38bdf8",
    "Villains": "#f43f5e",
    "Places": "#10b981",
    "Factions": "#a78bfa",
    "Creatures": "#fb7185",
    "Objects": "#facc15",
    "Books": "#c084fc",
    "Bases": "#34d399",
    "Maps": "#60a5fa",
    "Events": "#f97316",
}


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
        self.canvas.bind("<Configure>", self._draw)

    def _draw(self, *_args, **_kwargs) -> None:
        self.canvas.delete("all")
        width = max(self.canvas.winfo_width(), 360)
        height = max(self.canvas.winfo_height(), 106)

        self.canvas.create_rectangle(0, 0, width, height, fill=DASHBOARD_THEME.card_bg, outline="")
        self.canvas.create_line(48, height / 2, width - 48, height / 2, fill="#28415f", width=3, smooth=True)

        count = max(len(self._scenarios), 1)
        step = (width - 96) / count
        for index, scenario in enumerate(self._scenarios):
            x = 48 + step * index + step / 2
            y = height / 2
            r = 18
            self.canvas.create_oval(x - r - 6, y - r - 6, x + r + 6, y + r + 6, outline="#1e3a5f", width=2)
            self.canvas.create_oval(x - r, y - r, x + r, y + r, fill="#142740", outline="#66c0ff", width=2)
            self.canvas.create_text(x, y, text=str(index + 1), fill="#e5ecff", font=("Segoe UI", 11, "bold"))
            self.canvas.create_text(
                x,
                y + 32,
                text=_truncate(scenario.title, 18),
                fill=DASHBOARD_THEME.text_secondary,
                font=("Segoe UI", 10, "bold"),
                width=step - 10,
                justify="center",
                tags=(f"scenario:{scenario.title}",),
            )
            self.canvas.tag_bind(f"scenario:{scenario.title}", "<Button-1>", lambda _e, n=scenario.title: self._on_open_scenario(n))
            self.canvas.tag_bind(f"scenario:{scenario.title}", "<Enter>", lambda _e: self.canvas.configure(cursor="hand2"))
            self.canvas.tag_bind(f"scenario:{scenario.title}", "<Leave>", lambda _e: self.canvas.configure(cursor=""))


class EntityConstellation(ctk.CTkFrame):
    """Orbital entity graph that can open linked records on click."""

    def __init__(self, parent, *, links: Iterable[ScenarioEntityLink], on_open_entity: Callable[[str, str], None]):
        super().__init__(parent, fg_color="transparent")
        self._links = list(links)
        self._on_open_entity = on_open_entity

        self.canvas = tk.Canvas(
            self,
            height=210,
            bg=DASHBOARD_THEME.panel_bg,
            highlightthickness=0,
            bd=0,
        )
        self.canvas.pack(fill="x", expand=True)
        self.canvas.bind("<Configure>", self._draw)

    def _draw(self, *_args, **_kwargs) -> None:
        self.canvas.delete("all")
        width = max(self.canvas.winfo_width(), 340)
        height = max(self.canvas.winfo_height(), 210)
        cx, cy = width / 2, height / 2

        self.canvas.create_rectangle(0, 0, width, height, fill=DASHBOARD_THEME.panel_bg, outline="")
        for radius in (42, 68, 94):
            self.canvas.create_oval(cx - radius, cy - radius, cx + radius, cy + radius, outline="#1b3351", width=1)

        self.canvas.create_oval(cx - 30, cy - 30, cx + 30, cy + 30, fill="#25164b", outline="#8b5cf6", width=2)
        self.canvas.create_text(cx, cy - 6, text="Scene", fill="#f8f6ff", font=("Segoe UI", 12, "bold"))
        self.canvas.create_text(cx, cy + 12, text="Links", fill=DASHBOARD_THEME.text_secondary, font=("Segoe UI", 10))

        if not self._links:
            self.canvas.create_text(
                cx,
                height - 26,
                text="No linked entities for this scenario yet.",
                fill=DASHBOARD_THEME.text_secondary,
                font=("Segoe UI", 10),
            )
            return

        grouped: dict[str, list[ScenarioEntityLink]] = defaultdict(list)
        for link in self._links[:12]:
            grouped[link.entity_type].append(link)

        ordered = [link for links in grouped.values() for link in links]
        total = max(len(ordered), 1)
        for index, link in enumerate(ordered):
            angle = (math.tau / total) * index - math.pi / 2
            orbit = 92 if index % 2 == 0 else 68
            x = cx + math.cos(angle) * orbit
            y = cy + math.sin(angle) * orbit
            color = _ENTITY_COLORS.get(link.entity_type, "#67b6ff")
            tag = f"entity:{index}"
            self.canvas.create_line(cx, cy, x, y, fill="#22385a", width=2)
            self.canvas.create_oval(x - 16, y - 16, x + 16, y + 16, fill="#10233a", outline=color, width=2, tags=(tag,))
            self.canvas.create_text(x, y, text=_entity_glyph(link.entity_type), fill=color, font=("Segoe UI Emoji", 11, "bold"), tags=(tag,))
            self.canvas.create_text(
                x,
                y + 26,
                text=_truncate(link.name, 16),
                fill="#dbe7ff",
                font=("Segoe UI", 9, "bold"),
                width=84,
                justify="center",
                tags=(tag,),
            )
            self.canvas.tag_bind(tag, "<Button-1>", lambda _e, t=link.entity_type, n=link.name: self._on_open_entity(t, n))
            self.canvas.tag_bind(tag, "<Enter>", lambda _e: self.canvas.configure(cursor="hand2"))
            self.canvas.tag_bind(tag, "<Leave>", lambda _e: self.canvas.configure(cursor=""))


class CapsuleWrap(ctk.CTkFrame):
    def __init__(self, parent, *, items: Iterable[ScenarioEntityLink], on_open_entity: Callable[[str, str], None]):
        super().__init__(parent, fg_color="transparent")
        for column in range(3):
            self.grid_columnconfigure(column, weight=1)

        for index, link in enumerate(items):
            color = _ENTITY_COLORS.get(link.entity_type, DASHBOARD_THEME.accent_soft)
            ctk.CTkButton(
                self,
                text=f"{_entity_glyph(link.entity_type)} {link.name}",
                fg_color="#17263d",
                hover_color="#223a5f",
                border_width=1,
                border_color=color,
                text_color="#f2f6ff",
                command=lambda t=link.entity_type, n=link.name: on_open_entity(t, n),
            ).grid(row=index // 3, column=index % 3, sticky="ew", padx=4, pady=4)


def _truncate(value: str, limit: int) -> str:
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return text[: max(limit - 1, 0)].rstrip() + "…"


def _entity_glyph(entity_type: str) -> str:
    mapping = {
        "NPCs": "🧙",
        "PCs": "🛡",
        "Villains": "👁",
        "Places": "🗺",
        "Factions": "⚑",
        "Creatures": "🐉",
        "Objects": "✦",
        "Books": "📜",
        "Bases": "🏰",
        "Maps": "🧭",
        "Events": "⏳",
    }
    return mapping.get(entity_type, "✧")
