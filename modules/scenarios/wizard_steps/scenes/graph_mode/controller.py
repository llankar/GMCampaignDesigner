"""Graph mode planner root widget."""
from __future__ import annotations

import customtkinter as ctk

from .schema import SCENE_DEFAULT_TITLE, normalize_scene
from .state import GraphModeState
from .ui.canvas_view import GraphCanvasView
from .ui.properties_panel import PropertiesPanel
from .ui.toolbar import GraphToolbar


class GraphModePlanner(ctk.CTkFrame):
    """Root graph-mode planner widget, compatible with planner contracts."""

    def __init__(self, master):
        super().__init__(master, fg_color="transparent")
        self.state = GraphModeState()

        self.grid_columnconfigure(0, weight=3)
        self.grid_columnconfigure(1, weight=2)
        self.grid_rowconfigure(1, weight=1)

        self.toolbar = GraphToolbar(self)
        self.toolbar.grid(row=0, column=0, sticky="w", padx=(2, 8), pady=(0, 8))

        self.canvas_view = GraphCanvasView(self)
        self.canvas_view.grid(row=1, column=0, sticky="nsew", padx=(0, 8))

        self.properties_panel = PropertiesPanel(self)
        self.properties_panel.grid(row=1, column=1, sticky="nsew")

    def load_scenes(self, scenes):
        self.state.scenes = [normalize_scene(scene, i) for i, scene in enumerate(scenes or [], start=1)]
        if not self.state.scenes:
            self.canvas_view.load_scenes([])
            self.properties_panel.fields.title_var.set(SCENE_DEFAULT_TITLE)
            self.properties_panel.fields.objective_var.set("")
            self.properties_panel.fields.success_condition_var.set("")
            self.properties_panel.notes_box.delete("1.0", "end")
            return

        self.canvas_view.load_scenes(self.state.scenes)
        first = self.state.scenes[0]
        self.properties_panel.fields.title_var.set(first.get("title") or "")
        self.properties_panel.fields.objective_var.set(first.get("objective") or "")
        self.properties_panel.fields.success_condition_var.set(first.get("success_condition") or "")
        self.properties_panel.notes_box.delete("1.0", "end")
        self.properties_panel.notes_box.insert("1.0", first.get("notes") or "")

    def export_scenes(self):
        if not self.state.scenes:
            return []
        updated = []
        for i, scene in enumerate(self.state.scenes):
            row = dict(scene)
            node_id = row.get("id") or f"scene_{i+1}"
            canvas_node = self.canvas_view.nodes.get(node_id)
            if canvas_node:
                row["x"] = canvas_node.get("x", row.get("x", 0))
                row["y"] = canvas_node.get("y", row.get("y", 0))
            if i == 0:
                row["title"] = self.properties_panel.fields.title_var.get().strip() or row.get("title") or SCENE_DEFAULT_TITLE
                row["objective"] = self.properties_panel.fields.objective_var.get().strip()
                row["success_condition"] = self.properties_panel.fields.success_condition_var.get().strip()
                row["notes"] = self.properties_panel.notes_box.get("1.0", "end").strip()
            updated.append(row)
        return updated
