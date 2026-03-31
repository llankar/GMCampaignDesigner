"""Utilities for campaign entity constellation."""

from __future__ import annotations

import math
import tkinter as tk
from collections import defaultdict
from typing import Callable, Iterable

import customtkinter as ctk

from modules.scenarios.gm_screen.dashboard.styles.dashboard_theme import DASHBOARD_THEME
from ..data import ScenarioEntityLink

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

_GROUP_ORDER = ["Villains", "NPCs", "PCs", "Factions", "Places", "Bases", "Objects", "Creatures", "Maps", "Books", "Events"]


class EntityConstellation(ctk.CTkFrame):
    """Stylized orbital entity graph that centers the selected scenario."""

    def __init__(
        self,
        parent,
        *,
        scenario_title: str,
        links: Iterable[ScenarioEntityLink],
        on_open_entity: Callable[[str, str], None],
        accent: str | None = None,
    ):
        """Initialize the EntityConstellation instance."""
        super().__init__(parent, fg_color="#0d1728", corner_radius=20, border_width=1, border_color="#22395d")
        self._scenario_title = scenario_title
        self._links = list(links)
        self._on_open_entity = on_open_entity
        self._accent = accent or DASHBOARD_THEME.accent
        self._node_bounds: dict[str, tuple[float, float, float, float]] = {}
        self._hover_tag: str | None = None

        self.grid_columnconfigure(0, weight=1)

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=16, pady=(14, 8))
        header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            header,
            text="Relationship overview",
            text_color=DASHBOARD_THEME.text_primary,
            font=ctk.CTkFont(size=18, weight="bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(
            header,
            text="The active scenario anchors every linked entity cluster.",
            text_color=DASHBOARD_THEME.text_secondary,
            font=ctk.CTkFont(size=12),
            anchor="w",
        ).grid(row=1, column=0, sticky="w", pady=(4, 0))

        self._legend = ctk.CTkFrame(self, fg_color="transparent")
        self._legend.grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 6))

        canvas_wrap = ctk.CTkFrame(self, fg_color="#09111f", corner_radius=18)
        canvas_wrap.grid(row=2, column=0, sticky="nsew", padx=16, pady=(0, 16))
        canvas_wrap.grid_columnconfigure(0, weight=1)
        canvas_wrap.grid_rowconfigure(0, weight=1)

        self.canvas = tk.Canvas(
            canvas_wrap,
            height=380,
            bg="#09111f",
            highlightthickness=0,
            bd=0,
        )
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.canvas.bind("<Configure>", self._render)
        self.canvas.bind("<Motion>", self._handle_motion)
        self.canvas.bind("<Leave>", lambda _event: self._set_hover(None))
        self.after_idle(self._render)

    def _render(self, *_args, **_kwargs) -> None:
        """Render the operation."""
        canvas = getattr(self, "canvas", None)
        if canvas is None or not canvas.winfo_exists():
            return

        self._render_legend()
        self._node_bounds.clear()
        canvas.delete("all")
        width = max(canvas.winfo_width(), 420)
        height = max(canvas.winfo_height(), 380)
        cx, cy = width / 2, height / 2 + 6
        canvas.create_rectangle(0, 0, width, height, fill="#09111f", outline="")

        for radius, tint in ((78, "#12243f"), (126, "#102038"), (174, "#0d1a30")):
            canvas.create_oval(cx - radius, cy - radius, cx + radius, cy + radius, outline=tint, width=1)

        canvas.create_oval(cx - 42, cy - 42, cx + 42, cy + 42, fill="#24164c", outline=self._accent, width=3)
        canvas.create_oval(cx - 52, cy - 52, cx + 52, cy + 52, outline="#8b5cf6", width=2)
        canvas.create_text(cx, cy - 8, text="Scenario", fill="#f8f6ff", font=("Segoe UI", 12, "bold"))
        canvas.create_text(cx, cy + 14, text=_truncate(self._scenario_title, 22), fill="#d7dff5", font=("Segoe UI", 10, "bold"))

        if not self._links:
            canvas.create_text(
                cx,
                height - 30,
                text="No linked entities for this scenario yet.",
                fill=DASHBOARD_THEME.text_secondary,
                font=("Segoe UI", 10),
            )
            return

        grouped: dict[str, list[ScenarioEntityLink]] = defaultdict(list)
        for link in self._links[:18]:
            grouped[link.entity_type].append(link)

        type_order = [entity_type for entity_type in _GROUP_ORDER if grouped.get(entity_type)]
        type_order.extend(sorted(entity_type for entity_type in grouped if entity_type not in type_order))
        type_count = max(len(type_order), 1)
        band_radii = [100, 144, 186]

        node_index = 0
        for type_index, entity_type in enumerate(type_order):
            # Process each (type_index, entity_type) from enumerate(type_order).
            links = grouped[entity_type]
            start_angle = (math.tau / type_count) * type_index - math.pi / 2
            sweep = max(math.tau / type_count * 0.72, 0.42)
            radius = band_radii[min(type_index % len(band_radii), len(band_radii) - 1)]
            color = _ENTITY_COLORS.get(entity_type, "#67b6ff")

            if type_count > 1:
                canvas.create_arc(
                    cx - radius,
                    cy - radius,
                    cx + radius,
                    cy + radius,
                    start=math.degrees(-(start_angle + sweep / 2)),
                    extent=math.degrees(-sweep),
                    style="arc",
                    outline="#17304d",
                    width=2,
                )

            for local_index, link in enumerate(links):
                # Process each (local_index, link) from enumerate(links).
                fraction = (local_index + 1) / (len(links) + 1)
                angle = start_angle - sweep / 2 + sweep * fraction
                x = cx + math.cos(angle) * radius
                y = cy + math.sin(angle) * radius
                tag = f"entity:{node_index}"
                node_index += 1
                self._draw_link(canvas, cx, cy, x, y, color, entity_type, link, tag)

    def _draw_link(self, canvas, cx: float, cy: float, x: float, y: float, color: str, entity_type: str, link: ScenarioEntityLink, tag: str) -> None:
        """Internal helper for draw link."""
        canvas.create_line(cx, cy, x, y, fill="#1e3657", width=2)
        canvas.create_oval(x - 24, y - 24, x + 24, y + 24, fill="#10233a", outline="#25476d", width=2, tags=(tag, f"halo:{tag}"))
        canvas.create_oval(x - 20, y - 20, x + 20, y + 20, fill="#0e1d31", outline=color, width=3, tags=(tag,))
        canvas.create_text(x, y - 1, text=_entity_glyph(entity_type), fill=color, font=("Segoe UI Emoji", 12, "bold"), tags=(tag,))
        canvas.create_text(
            x,
            y + 30,
            text=_truncate(link.name, 17),
            fill="#e7f0ff",
            font=("Segoe UI", 9, "bold"),
            width=92,
            justify="center",
            tags=(tag,),
        )
        canvas.tag_bind(tag, "<Button-1>", lambda _e, t=link.entity_type, n=link.name: self._on_open_entity(t, n))
        canvas.tag_bind(tag, "<Enter>", lambda _e, current=tag: self._set_hover(current))
        canvas.tag_bind(tag, "<Leave>", lambda _e: self._set_hover(None))
        self._node_bounds[tag] = (x - 30, y - 30, x + 30, y + 42)

    def _render_legend(self) -> None:
        """Render legend."""
        for child in self._legend.winfo_children():
            child.destroy()

        shown_types = [entity_type for entity_type in _GROUP_ORDER if any(link.entity_type == entity_type for link in self._links)]
        shown_types.extend(sorted({link.entity_type for link in self._links if link.entity_type not in shown_types}))
        if not shown_types:
            return

        for index, entity_type in enumerate(shown_types[:6]):
            color = _ENTITY_COLORS.get(entity_type, "#67b6ff")
            pill = ctk.CTkFrame(self._legend, fg_color="#10233a", corner_radius=999, border_width=1, border_color="#25476d")
            pill.grid(row=index // 3, column=index % 3, sticky="w", padx=(0, 8), pady=(0, 8))
            ctk.CTkLabel(pill, text="●", text_color=color, font=ctk.CTkFont(size=12, weight="bold")).grid(row=0, column=0, padx=(10, 6), pady=5)
            ctk.CTkLabel(
                pill,
                text=entity_type,
                text_color="#eaf2ff",
                font=ctk.CTkFont(size=11, weight="bold"),
            ).grid(row=0, column=1, padx=(0, 10), pady=5)

    def _handle_motion(self, event) -> None:
        """Internal helper for handle motion."""
        for tag, (x1, y1, x2, y2) in self._node_bounds.items():
            if x1 <= event.x <= x2 and y1 <= event.y <= y2:
                self._set_hover(tag)
                return
        self._set_hover(None)

    def _set_hover(self, tag: str | None) -> None:
        """Set hover."""
        if self._hover_tag == tag:
            return
        canvas = getattr(self, "canvas", None)
        if canvas is None or not canvas.winfo_exists():
            return
        if self._hover_tag is not None:
            canvas.itemconfigure(f"halo:{self._hover_tag}", outline="#25476d", width=2)
        self._hover_tag = tag
        if tag is not None:
            canvas.itemconfigure(f"halo:{tag}", outline="#dbeafe", width=3)
            canvas.configure(cursor="hand2")
        else:
            canvas.configure(cursor="")


def _truncate(value: str, limit: int) -> str:
    """Internal helper for truncate."""
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return text[: max(limit - 1, 0)].rstrip() + "…"


def _entity_glyph(entity_type: str) -> str:
    """Internal helper for entity glyph."""
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
