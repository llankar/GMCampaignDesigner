"""Root passive view for GM Screen 2 desktop panel composition."""

from __future__ import annotations

import customtkinter as ctk

from modules.scenarios.gm_screen2.app.gm_screen2_controller import GMScreen2Controller
from modules.scenarios.gm_screen2.ui.layout.desktop_layout_engine import DesktopLayoutEngine
from modules.scenarios.gm_screen2.ui.panels import (
    EntitiesPanelView,
    NotesPanelView,
    OverviewPanelView,
    QuickReferencePanelView,
    TimelinePanelView,
)


class GMScreen2RootView(ctk.CTkFrame):
    """Builds desktop layout from controller state only."""

    PANEL_TYPES = {
        "overview": OverviewPanelView,
        "entities": EntitiesPanelView,
        "notes": NotesPanelView,
        "timeline": TimelinePanelView,
        "quick_reference": QuickReferencePanelView,
    }

    def __init__(self, master, controller: GMScreen2Controller, **kwargs):
        super().__init__(master, **kwargs)
        self.controller = controller
        self._layout_engine = DesktopLayoutEngine()
        self._panel_widgets = {
            panel_id: panel_cls(self)
            for panel_id, panel_cls in self.PANEL_TYPES.items()
        }
        self.controller.events.subscribe("state_changed", self.render_from_state)
        self.render_from_state()

    def render_from_state(self) -> None:
        """Render all panel widgets from current controller state."""
        state = self.controller.state
        panel_order = state.layout.panel_order
        hidden_panels = state.layout.hidden_panels
        geometries = self._layout_engine.compute(panel_order, state.layout.split_ratios, hidden_panels)

        for panel_widget in self._panel_widgets.values():
            panel_widget.place_forget()

        geometry_by_panel = {geometry.panel_id: geometry for geometry in geometries}
        for panel_id, payload in state.panel_payloads.items():
            panel_widget = self._panel_widgets.get(panel_id)
            geometry = geometry_by_panel.get(panel_id)
            if panel_widget is None or geometry is None:
                continue
            panel_widget.render_payload(payload)
            panel_widget.place(
                relx=geometry.relx,
                rely=geometry.rely,
                relwidth=geometry.relwidth,
                relheight=geometry.relheight,
            )
