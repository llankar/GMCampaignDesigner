from __future__ import annotations

import math
import tkinter as tk
from collections import defaultdict
from typing import Callable, Iterable

import customtkinter as ctk

from modules.scenarios.gm_screen.dashboard.styles.dashboard_theme import DASHBOARD_THEME
from .data import ScenarioEntityLink


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


class EntityConstellation(ctk.CTkFrame):
    """Orbital entity graph that can open linked records on click."""

    def __init__(self, parent, *, links: Iterable[ScenarioEntityLink], on_open_entity: Callable[[str, str], None]):
        super().__init__(parent, fg_color="transparent")
        self._links = list(links)
        self._on_open_entity = on_open_entity

        self.canvas = tk.Canvas(
            self,
            height=340,
            bg=DASHBOARD_THEME.panel_bg,
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
        width = max(canvas.winfo_width(), 340)
        height = max(canvas.winfo_height(), 340)
        cx, cy = width / 2, height / 2

        self._draw_background(canvas, width, height, cx, cy)
        if not self._links:
            canvas.create_text(
                cx,
                height - 26,
                text="No linked entities for this scenario yet.",
                fill=DASHBOARD_THEME.text_secondary,
                font=("Segoe UI", 10),
            )
            return

        grouped: dict[str, list[ScenarioEntityLink]] = defaultdict(list)
        for link in self._links[:14]:
            grouped[link.entity_type].append(link)

        ordered_groups = sorted(grouped.items(), key=lambda item: (-len(item[1]), item[0]))
        nodes = [link for _, links in ordered_groups for link in links]
        total = max(len(nodes), 1)

        for index, link in enumerate(nodes):
            angle = (math.tau / total) * index - math.pi / 2
            band = 0 if index % 3 == 0 else (1 if index % 3 == 1 else 2)
            orbit = self._orbit_radius(width, height, band)
            x = cx + math.cos(angle) * orbit
            y = cy + math.sin(angle) * orbit
            color = _ENTITY_COLORS.get(link.entity_type, "#67b6ff")
            tag = f"entity:{index}"
            canvas.create_line(cx, cy, x, y, fill="#1c3656", width=2)
            canvas.create_oval(x - 19, y - 19, x + 19, y + 19, fill="#0d1f33", outline="#081321", width=5)
            canvas.create_oval(x - 16, y - 16, x + 16, y + 16, fill="#10233a", outline=color, width=2, tags=(tag,))
            canvas.create_text(x, y, text=_entity_glyph(link.entity_type), fill=color, font=("Segoe UI Emoji", 11, "bold"), tags=(tag,))
            canvas.create_text(
                x,
                y + 28,
                text=_truncate(link.name, 16),
                fill="#dbe7ff",
                font=("Segoe UI", 9, "bold"),
                width=84,
                justify="center",
                tags=(tag,),
            )
            canvas.tag_bind(tag, "<Button-1>", lambda _e, t=link.entity_type, n=link.name: self._on_open_entity(t, n))
            canvas.tag_bind(tag, "<Enter>", lambda _e: canvas.configure(cursor="hand2"))
            canvas.tag_bind(tag, "<Leave>", lambda _e: canvas.configure(cursor=""))

        legend_items = [f"{entity_type} × {len(links)}" for entity_type, links in ordered_groups[:4]]
        canvas.create_text(
            cx,
            height - 20,
            text="   •   ".join(legend_items),
            fill="#92a9ca",
            font=("Segoe UI", 9, "bold"),
        )

    def _draw_background(self, canvas: tk.Canvas, width: int, height: int, cx: float, cy: float) -> None:
        canvas.create_rectangle(0, 0, width, height, fill=DASHBOARD_THEME.panel_bg, outline="")
        for index in range(18):
            x = ((index * 97) % max(width - 10, 1)) + 6
            y = ((index * 53) % max(height - 10, 1)) + 6
            radius = 1 if index % 4 else 2
            color = "#1d3552" if radius == 1 else "#365b87"
            canvas.create_oval(x - radius, y - radius, x + radius, y + radius, fill=color, outline="")

        for radius, outline in ((52, "#132540"), (86, "#17324f"), (122, "#1c3d60")):
            canvas.create_oval(cx - radius, cy - radius, cx + radius, cy + radius, outline=outline, width=1)

        canvas.create_oval(cx - 42, cy - 42, cx + 42, cy + 42, fill="#170f31", outline="#7c3aed", width=2)
        canvas.create_oval(cx - 26, cy - 26, cx + 26, cy + 26, fill="#261657", outline="#ad7bff", width=2)
        canvas.create_text(cx, cy - 7, text="Scenario", fill="#f8f6ff", font=("Segoe UI", 13, "bold"))
        canvas.create_text(cx, cy + 15, text="Signal Core", fill=DASHBOARD_THEME.text_secondary, font=("Segoe UI", 10))

    def _orbit_radius(self, width: int, height: int, band: int) -> float:
        limit = min(width, height) / 2
        if band == 0:
            return min(max(82, limit * 0.38), max(limit - 44, 82))
        if band == 1:
            return min(max(102, limit * 0.48), max(limit - 28, 102))
        return min(max(62, limit * 0.28), max(limit - 64, 62))


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
