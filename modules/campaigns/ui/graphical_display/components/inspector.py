from __future__ import annotations

from collections import Counter
from typing import Callable

import customtkinter as ctk

from modules.scenarios.gm_screen.dashboard.styles.dashboard_theme import DASHBOARD_THEME
from ..data import CampaignGraphScenario
from ..visuals import EntityConstellation


class ScenarioSpotlight(ctk.CTkFrame):
    """High-contrast scenario spotlight with synopsis, telemetry, and entity map."""

    def __init__(
        self,
        parent,
        *,
        scenario: CampaignGraphScenario,
        on_open_scenario: Callable[[str], None],
        on_open_entity: Callable[[str, str], None],
    ):
        super().__init__(parent, fg_color="#08111f", corner_radius=24, border_width=1, border_color="#274264")
        self._scenario = scenario
        self.grid_columnconfigure(0, weight=3)
        self.grid_columnconfigure(1, weight=2)
        self.grid_rowconfigure(1, weight=1)

        self._build_header(on_open_scenario)
        self._build_story_column()
        self._build_graph_column(on_open_entity)

    def _build_header(self, on_open_scenario: Callable[[str], None]) -> None:
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, columnspan=2, sticky="ew", padx=18, pady=(18, 10))
        header.grid_columnconfigure(0, weight=1)

        eyebrow = ctk.CTkLabel(
            header,
            text="SCENARIO SPOTLIGHT",
            text_color="#8bd5ff",
            font=ctk.CTkFont(size=11, weight="bold"),
            anchor="w",
        )
        eyebrow.grid(row=0, column=0, sticky="w")

        ctk.CTkLabel(
            header,
            text=self._scenario.title,
            text_color=DASHBOARD_THEME.text_primary,
            font=ctk.CTkFont(size=24, weight="bold"),
            anchor="w",
        ).grid(row=1, column=0, sticky="w", pady=(4, 0))

        ctk.CTkButton(
            header,
            text="Open scenario",
            width=132,
            fg_color=DASHBOARD_THEME.accent,
            hover_color=DASHBOARD_THEME.accent_hover,
            command=lambda: on_open_scenario(self._scenario.title),
        ).grid(row=0, column=1, rowspan=2, sticky="e")

    def _build_story_column(self) -> None:
        story = ctk.CTkFrame(self, fg_color="#0d1728", corner_radius=20, border_width=1, border_color="#1f3655")
        story.grid(row=1, column=0, sticky="nsew", padx=(18, 10), pady=(0, 18))
        story.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            story,
            text="Synopsis",
            text_color="#7dd3fc",
            font=ctk.CTkFont(size=12, weight="bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="w", padx=16, pady=(16, 6))

        summary_label = ctk.CTkLabel(
            story,
            text=self._scenario.summary or "No synopsis written yet for this scenario.",
            text_color=DASHBOARD_THEME.text_secondary,
            justify="left",
            anchor="w",
        )
        summary_label.grid(row=1, column=0, sticky="ew", padx=16)
        self._bind_wraplength(story, summary_label, horizontal_padding=44, minimum=260)

        telemetry = ctk.CTkFrame(story, fg_color="transparent")
        telemetry.grid(row=2, column=0, sticky="ew", padx=16, pady=(14, 14))
        for column in range(3):
            telemetry.grid_columnconfigure(column, weight=1)

        metrics = [
            ("Total links", str(len(self._scenario.entity_links)), "#8b5cf6"),
            ("Entity types", str(len({link.entity_type for link in self._scenario.entity_links})), "#38bdf8"),
            ("Scene energy", _energy_label(len(self._scenario.entity_links)), "#f59e0b"),
        ]
        for column, (label, value, accent) in enumerate(metrics):
            _MetricCard(telemetry, title=label, value=value, accent=accent).grid(
                row=0,
                column=column,
                sticky="ew",
                padx=(0 if column == 0 else 6, 0 if column == len(metrics) - 1 else 6),
            )

        ctk.CTkLabel(
            story,
            text="Entity signal",
            text_color="#c084fc",
            font=ctk.CTkFont(size=12, weight="bold"),
            anchor="w",
        ).grid(row=3, column=0, sticky="w", padx=16, pady=(2, 6))

        LinkSummaryBar(story, scenario=self._scenario).grid(row=4, column=0, sticky="ew", padx=16, pady=(0, 16))

    def _build_graph_column(self, on_open_entity: Callable[[str, str], None]) -> None:
        graph = ctk.CTkFrame(self, fg_color="#091423", corner_radius=20, border_width=1, border_color="#1f3655")
        graph.grid(row=1, column=1, sticky="nsew", padx=(10, 18), pady=(0, 18))
        graph.grid_columnconfigure(0, weight=1)
        graph.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(
            graph,
            text="Constellation",
            text_color="#f0abfc",
            font=ctk.CTkFont(size=12, weight="bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="w", padx=16, pady=(16, 6))

        EntityConstellation(graph, links=self._scenario.entity_links, on_open_entity=on_open_entity).grid(
            row=1,
            column=0,
            sticky="nsew",
            padx=10,
            pady=(0, 10),
        )

        ctk.CTkLabel(
            graph,
            text="Click any orbiting node to jump straight into the linked record.",
            text_color=DASHBOARD_THEME.text_secondary,
            font=ctk.CTkFont(size=11),
            justify="left",
            anchor="w",
        ).grid(row=2, column=0, sticky="ew", padx=16, pady=(0, 16))

    def _bind_wraplength(self, parent, label, *, horizontal_padding: int = 40, minimum: int = 240) -> None:
        def _update(_event=None):
            try:
                label.configure(wraplength=max(minimum, parent.winfo_width() - horizontal_padding))
            except Exception:
                pass

        parent.bind("<Configure>", _update, add="+")
        parent.after(50, _update)


class LinkSummaryBar(ctk.CTkFrame):
    def __init__(self, parent, *, scenario: CampaignGraphScenario):
        super().__init__(parent, fg_color="transparent")
        counts = Counter(link.entity_type for link in scenario.entity_links)
        if not counts:
            ctk.CTkLabel(
                self,
                text="No linked entities yet — this is a perfect blank canvas.",
                text_color=DASHBOARD_THEME.text_secondary,
                anchor="w",
                justify="left",
            ).grid(row=0, column=0, sticky="w")
            return

        ordered = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
        for column, (entity_type, total) in enumerate(ordered[:6]):
            pill = ctk.CTkFrame(self, fg_color="#13233a", corner_radius=999, border_width=1, border_color="#22395d")
            pill.grid(row=0, column=column, sticky="w", padx=(0, 8), pady=4)
            ctk.CTkLabel(
                pill,
                text=f"{entity_type} · {total}",
                text_color="#dceafe",
                font=ctk.CTkFont(size=11, weight="bold"),
            ).pack(padx=12, pady=6)


class _MetricCard(ctk.CTkFrame):
    def __init__(self, parent, *, title: str, value: str, accent: str):
        super().__init__(parent, fg_color="#101d31", corner_radius=18, border_width=1, border_color="#233a59")
        self.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            self,
            text=title.upper(),
            text_color=accent,
            font=ctk.CTkFont(size=10, weight="bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="w", padx=12, pady=(10, 2))
        ctk.CTkLabel(
            self,
            text=value,
            text_color=DASHBOARD_THEME.text_primary,
            font=ctk.CTkFont(size=18, weight="bold"),
            anchor="w",
        ).grid(row=1, column=0, sticky="w", padx=12, pady=(0, 10))


def _energy_label(link_count: int) -> str:
    if link_count >= 8:
        return "Epic"
    if link_count >= 4:
        return "Rising"
    if link_count >= 1:
        return "Focused"
    return "Quiet"
