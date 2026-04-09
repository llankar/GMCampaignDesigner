"""Workspace root surface for GM Screen 2."""

from __future__ import annotations

import customtkinter as ctk

from modules.scenarios.gm_screen2.app.gm_screen2_controller import GMScreen2Controller
from modules.scenarios.gm_screen2.ui.panels import PANEL_TYPES
from modules.scenarios.gm_screen2.ui.workspace.compositor import WorkspaceCompositor


class WorkspaceRootSurface(ctk.CTkFrame):
    """Root frame that keeps UI passive and reflects controller state."""

    def __init__(self, master, controller: GMScreen2Controller, **kwargs):
        super().__init__(master, **kwargs)
        self.controller = controller
        self._panel_widgets = {panel_id: panel_cls(self) for panel_id, panel_cls in PANEL_TYPES.items()}
        self._compositor = WorkspaceCompositor(self, self._on_resize_split, self._on_activate_panel)
        self.controller.events.subscribe("state_changed", lambda _payload: self.render_from_state())
        self.render_from_state()

    def render_from_state(self) -> None:
        state = self.controller.state
        for panel_id, payload in state.panel_payloads.items():
            widget = self._panel_widgets.get(panel_id)
            if widget is not None:
                widget.render_payload(payload)
        visibility = {panel_id: instance.visible for panel_id, instance in state.layout.panel_instances.items()}
        self._compositor.rebuild(state.layout.root, self._panel_widgets, visibility)

    def _on_resize_split(self, split_id: str, ratio: float) -> None:
        self.controller.docking.resize_split(split_id, ratio)

    def _on_activate_panel(self, zone_id: str, panel_id: str) -> None:
        zone = self.controller.state.layout
        # passive UI dispatch: move selected panel focus only
        self.controller.update_state(selected_panel_id=panel_id)
