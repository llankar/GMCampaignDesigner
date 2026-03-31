"""Browser UI for scenario entities."""
from __future__ import annotations

from collections import OrderedDict
from typing import Callable, Iterable

import customtkinter as ctk

from modules.scenarios.gm_screen.dashboard.styles.dashboard_theme import DASHBOARD_THEME
from ...data import ScenarioEntityLink

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

_ENTITY_GLYPHS = {
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

_GROUP_ORDER = ["Villains", "NPCs", "PCs", "Factions", "Places", "Bases", "Objects", "Creatures", "Maps", "Books", "Events"]


class ScenarioEntityBrowser(ctk.CTkFrame):
    """High-contrast entity browser that replaces the scenario graph with actionable UI."""

    def __init__(
        self,
        parent,
        *,
        scenario_title: str,
        links: Iterable[ScenarioEntityLink],
        on_open_entity: Callable[[str, str], None],
    ):
        """Initialize the ScenarioEntityBrowser instance."""
        super().__init__(parent, fg_color=DASHBOARD_THEME.panel_alt_bg, corner_radius=20, border_width=1, border_color=DASHBOARD_THEME.card_border)
        self._scenario_title = scenario_title
        self._groups = group_scenario_entities(links)
        self._on_open_entity = on_open_entity

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        self._build_header()
        self._build_overview()
        self._build_body()

    def _build_header(self) -> None:
        """Build header."""
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=16, pady=(14, 10))
        header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            header,
            text="Scenario entities",
            text_color=DASHBOARD_THEME.text_primary,
            font=ctk.CTkFont(size=18, weight="bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(
            header,
            text=f"A curated roster of the forces orbiting {self._scenario_title}.",
            text_color=DASHBOARD_THEME.text_secondary,
            font=ctk.CTkFont(size=12),
            anchor="w",
        ).grid(row=1, column=0, sticky="w", pady=(4, 0))

    def _build_overview(self) -> None:
        """Build overview."""
        overview = ctk.CTkFrame(self, fg_color=DASHBOARD_THEME.panel_bg, corner_radius=18, border_width=1, border_color=DASHBOARD_THEME.card_border)
        overview.grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 12))
        for column in range(3):
            overview.grid_columnconfigure(column, weight=1)

        total_entities = sum(len(group["entities"]) for group in self._groups)
        dominant = self._groups[0]["entity_type"] if self._groups else "Unassigned"
        ctk.CTkLabel(
            overview,
            text="ENTITY LOADOUT",
            text_color="#8fb0dd",
            font=ctk.CTkFont(size=10, weight="bold"),
            anchor="w",
        ).grid(row=0, column=0, columnspan=3, sticky="w", padx=14, pady=(12, 2))

        metrics = [
            ("Linked entities", str(total_entities), "#7dd3fc"),
            ("Active clusters", str(len(self._groups)), "#c084fc"),
            ("Primary pressure", dominant, _entity_color(dominant)),
        ]
        for index, (label, value, accent) in enumerate(metrics):
            # Process each (index, (label, value, accent)) from enumerate(metrics).
            card = ctk.CTkFrame(overview, fg_color=DASHBOARD_THEME.panel_alt_bg, corner_radius=16, border_width=1, border_color=DASHBOARD_THEME.card_border)
            card.grid(row=1, column=index, sticky="nsew", padx=8, pady=(6, 12))
            card.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(
                card,
                text=label.upper(),
                text_color=accent,
                font=ctk.CTkFont(size=10, weight="bold"),
                anchor="w",
            ).grid(row=0, column=0, sticky="w", padx=12, pady=(10, 4))
            ctk.CTkLabel(
                card,
                text=value,
                text_color=DASHBOARD_THEME.text_primary,
                font=ctk.CTkFont(size=16, weight="bold"),
                anchor="w",
            ).grid(row=1, column=0, sticky="w", padx=12, pady=(0, 10))

    def _build_body(self) -> None:
        """Build body."""
        if not self._groups:
            # Handle the branch where groups is unavailable.
            empty = ctk.CTkFrame(self, fg_color=DASHBOARD_THEME.panel_bg, corner_radius=18)
            empty.grid(row=2, column=0, sticky="nsew", padx=16, pady=(0, 16))
            empty.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(
                empty,
                text="No scenario entities linked yet.",
                text_color=DASHBOARD_THEME.text_primary,
                font=ctk.CTkFont(size=18, weight="bold"),
            ).grid(row=0, column=0, pady=(32, 8), padx=24)
            ctk.CTkLabel(
                empty,
                text="Link NPCs, places, factions, or villains to turn this panel into a tactical roster.",
                text_color=DASHBOARD_THEME.text_secondary,
                font=ctk.CTkFont(size=12),
                wraplength=440,
                justify="center",
            ).grid(row=1, column=0, pady=(0, 32), padx=24)
            return

        body = ctk.CTkScrollableFrame(self, fg_color=DASHBOARD_THEME.panel_bg, corner_radius=18)
        body.grid(row=2, column=0, sticky="nsew", padx=16, pady=(0, 16))
        body.grid_columnconfigure(0, weight=1)

        for row, group in enumerate(self._groups):
            # Process each (row, group) from enumerate(_groups).
            accent = _entity_color(group["entity_type"])
            section = ctk.CTkFrame(body, fg_color=DASHBOARD_THEME.panel_alt_bg, corner_radius=18, border_width=1, border_color=DASHBOARD_THEME.card_border)
            section.grid(row=row, column=0, sticky="ew", pady=(0, 12))
            section.grid_columnconfigure(0, weight=1)

            header = ctk.CTkFrame(section, fg_color="transparent")
            header.grid(row=0, column=0, sticky="ew", padx=14, pady=(14, 8))
            header.grid_columnconfigure(1, weight=1)
            ctk.CTkLabel(
                header,
                text=_entity_glyph(group["entity_type"]),
                text_color=accent,
                font=ctk.CTkFont(size=18, weight="bold"),
            ).grid(row=0, column=0, rowspan=2, sticky="n", padx=(0, 10))
            ctk.CTkLabel(
                header,
                text=group["entity_type"],
                text_color=DASHBOARD_THEME.text_primary,
                font=ctk.CTkFont(size=16, weight="bold"),
                anchor="w",
            ).grid(row=0, column=1, sticky="w")
            ctk.CTkLabel(
                header,
                text=f"{len(group['entities'])} linked {group['entity_type'].lower()}",
                text_color=DASHBOARD_THEME.text_secondary,
                font=ctk.CTkFont(size=11),
                anchor="w",
            ).grid(row=1, column=1, sticky="w", pady=(2, 0))
            ctk.CTkLabel(
                header,
                text=f"Focus {row + 1}",
                fg_color=DASHBOARD_THEME.button_fg,
                corner_radius=999,
                padx=10,
                pady=4,
                text_color="#dceaff",
                font=ctk.CTkFont(size=10, weight="bold"),
            ).grid(row=0, column=2, rowspan=2, sticky="e")

            entity_grid = ctk.CTkFrame(section, fg_color="transparent")
            entity_grid.grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 14))
            for column in range(2):
                entity_grid.grid_columnconfigure(column, weight=1)

            for index, entity_name in enumerate(group["entities"]):
                # Process each (index, entity_name) from enumerate(group['entities']).
                card = ctk.CTkFrame(entity_grid, fg_color=DASHBOARD_THEME.panel_bg, corner_radius=14, border_width=1, border_color=DASHBOARD_THEME.card_border)
                card.grid(row=index // 2, column=index % 2, sticky="ew", padx=(0, 10), pady=(0, 10))
                card.grid_columnconfigure(0, weight=1)
                ctk.CTkLabel(
                    card,
                    text=group["entity_type"].upper(),
                    text_color=accent,
                    font=ctk.CTkFont(size=10, weight="bold"),
                    anchor="w",
                ).grid(row=0, column=0, sticky="w", padx=12, pady=(10, 2))
                ctk.CTkButton(
                    card,
                    text=entity_name,
                    command=lambda entity_type=group["entity_type"], name=entity_name: self._on_open_entity(entity_type, name),
                    fg_color="transparent",
                    hover_color=DASHBOARD_THEME.button_hover,
                    text_color=DASHBOARD_THEME.text_primary,
                    anchor="w",
                    border_spacing=0,
                    height=30,
                ).grid(row=1, column=0, sticky="ew", padx=8, pady=(0, 8))


def group_scenario_entities(links: Iterable[ScenarioEntityLink]) -> list[dict[str, object]]:
    """Group scenario entities."""
    grouped: OrderedDict[str, OrderedDict[str, None]] = OrderedDict()
    for link in links:
        # Process each link from links.
        entity_type = str(getattr(link, "entity_type", "") or "").strip() or "Other"
        entity_name = str(getattr(link, "name", "") or "").strip()
        if not entity_name:
            continue
        group = grouped.setdefault(entity_type, OrderedDict())
        group.setdefault(entity_name, None)

    ordered_types = [entity_type for entity_type in _GROUP_ORDER if entity_type in grouped]
    ordered_types.extend(sorted(entity_type for entity_type in grouped if entity_type not in ordered_types))

    return [
        {"entity_type": entity_type, "entities": list(grouped[entity_type].keys())}
        for entity_type in ordered_types
    ]


def _entity_color(entity_type: str) -> str:
    """Internal helper for entity color."""
    return _ENTITY_COLORS.get(entity_type, "#67b6ff")


def _entity_glyph(entity_type: str) -> str:
    """Internal helper for entity glyph."""
    return _ENTITY_GLYPHS.get(entity_type, "✧")
