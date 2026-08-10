"""Scenario-wizard styled character graph embedded in the GM scenario board."""

from __future__ import annotations

from typing import Any, Mapping

import customtkinter as ctk

from modules.scenarios.scenario_character_graph import ScenarioCharacterGraphEditor


class ScenarioBoardCharacterGraph(ScenarioCharacterGraphEditor):
    """A presentation-focused variant of the wizard's character graph."""

    def init_toolbar(self) -> None:
        """Replace editing actions with a compact viewing hint."""
        toolbar = ctk.CTkFrame(self, fg_color="#172536", corner_radius=0)
        toolbar.pack(fill="x")
        ctk.CTkLabel(
            toolbar,
            text="NPC RELATIONSHIPS",
            text_color="#f3f7fb",
            font=ctk.CTkFont(size=12, weight="bold"),
        ).pack(side="left", padx=12, pady=8)
        ctk.CTkLabel(
            toolbar,
            text="Drag to inspect · Ctrl + wheel to zoom",
            text_color="#9db4d1",
            font=ctk.CTkFont(size=10),
        ).pack(side="right", padx=12, pady=8)

    def on_right_click(self, _event):
        """Keep the board representation free of destructive context actions."""
        return "break"

    def open_character_editor(self, _event):
        """Prevent the presentation-only board from opening an editable record."""
        return "break"


def create_scenario_character_graph(
    master,
    *,
    graph_data: Mapping[str, Any],
    wrappers: Mapping[str, object],
) -> ScenarioBoardCharacterGraph | None:
    """Create the graph when its data and required entity stores are available."""
    if not graph_data.get("nodes"):
        return None
    required = ("NPCs", "PCs", "Factions")
    if any(wrappers.get(key) is None for key in required):
        return None
    return ScenarioBoardCharacterGraph(
        master,
        npc_wrapper=wrappers["NPCs"],
        pc_wrapper=wrappers["PCs"],
        faction_wrapper=wrappers["Factions"],
        graph_data=dict(graph_data),
        background_style="scene_flow",
        node_style="modern",
    )
