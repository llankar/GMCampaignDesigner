"""Window for campaign."""

from __future__ import annotations

import customtkinter as ctk

from modules.helpers import theme_manager
from modules.helpers.window_helper import position_window_at_top
from .panel import CampaignGraphPanel


class CampaignGraphWindow(ctk.CTkToplevel):
    def __init__(self, master, *, campaign_wrapper=None, scenario_wrapper=None):
        """Initialize the CampaignGraphWindow instance."""
        super().__init__(master)
        self.title("Campaign Overview")
        self.geometry("1440x940")
        self.minsize(1100, 760)
        self.configure(fg_color=theme_manager.get_tokens().get("panel_bg", "#111c2a"))
        position_window_at_top(self)
        self._theme_listener_unsub = theme_manager.register_theme_change_listener(self._on_theme_changed)

        panel = CampaignGraphPanel(
            self,
            campaign_wrapper=campaign_wrapper,
            scenario_wrapper=scenario_wrapper,
        )
        panel.pack(fill="both", expand=True)
        self.panel = panel
        self.bind("<Destroy>", self._on_destroy, add="+")

    def _on_destroy(self, _event=None) -> None:
        """Handle destroy."""
        unsub = getattr(self, "_theme_listener_unsub", None)
        if callable(unsub):
            unsub()
            self._theme_listener_unsub = None
        parent = getattr(self, "master", None)
        if parent is not None and getattr(parent, "_campaign_graph_window", None) is self:
            parent._campaign_graph_window = None

    def _on_theme_changed(self, _theme_key: str) -> None:
        """Handle theme changed."""
        self.configure(fg_color=theme_manager.get_tokens().get("panel_bg", "#111c2a"))
        panel = getattr(self, "panel", None)
        if panel is not None and hasattr(panel, "refresh_theme"):
            panel.refresh_theme()
