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
        self._pending_ui_update: str | None = None

        self.grid_columnconfigure(0, weight=3)
        self.grid_columnconfigure(1, weight=2)
        self.grid_rowconfigure(1, weight=1)

        self.toolbar = GraphToolbar(self)
        self.toolbar.grid(row=0, column=0, sticky="w", padx=(2, 8), pady=(0, 8))

        self.canvas_view = GraphCanvasView(self)
        self.canvas_view.grid(row=1, column=0, sticky="nsew", padx=(0, 8))

        self.properties_panel = PropertiesPanel(self)
        self.properties_panel.grid(row=1, column=1, sticky="nsew")
        self.properties_panel.on_change = self._on_properties_change

        self.canvas_view.on_selection_change = self._on_canvas_selection_changed

    def load_scenes(self, scenes):
        self.state.scenes = [normalize_scene(scene, i) for i, scene in enumerate(scenes or [], start=1)]
        self.state.edges = []
        self.canvas_view.load_scenes(self.state.scenes)
        self.state.edges = [
            {"id": eid, "source": src, "target": dst, "label": "", "condition_type": "always", "condition_value": ""}
            for eid, src, dst in self.canvas_view.edges
        ]
        self._refresh_properties_from_state()

    def _on_canvas_selection_changed(self, node_id: str | None, edge_id: str | None):
        self.state.set_selected_node(node_id)
        self.state.set_selected_edge(edge_id)
        self._refresh_properties_from_state()

    def _refresh_properties_from_state(self):
        if self.state.selected_node_id:
            node = self.state.selected_node() or {}
            self.properties_panel.load_node(node)
        elif self.state.selected_edge_id:
            edge = self.state.selected_edge() or {}
            self.properties_panel.load_edge(edge)
        else:
            self.properties_panel.show_empty()
        self.properties_panel.set_dirty(self.state.dirty)

    def _on_properties_change(self, field: str, value):
        if self._pending_ui_update:
            self.after_cancel(self._pending_ui_update)
        self._pending_ui_update = self.after(150, lambda: self._apply_properties_change(field, value))

    def _apply_properties_change(self, field: str, value):
        self._pending_ui_update = None
        if self.state.selected_node_id:
            self.state.update_selected_node_field(field, value)
            if field == "title":
                node = self.state.selected_node()
                if node and node.get("id") in self.canvas_view.nodes:
                    self.canvas_view.nodes[node["id"]]["title"] = value
                    self.canvas_view._draw_node(node["id"])
        elif self.state.selected_edge_id:
            self.state.update_selected_edge_field(field, value)
        self.properties_panel.set_dirty(self.state.dirty)

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
            updated.append(row)
        return updated
