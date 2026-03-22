from __future__ import annotations

import customtkinter as ctk

from modules.helpers.window_helper import position_window_at_top
from .panel import CampaignGraphPanel


class CampaignGraphWindow(ctk.CTkToplevel):
    def __init__(self, master, *, campaign_wrapper=None, scenario_wrapper=None):
        super().__init__(master)
        self.title("Campaign Constellation")
        self.geometry("1440x940")
        self.minsize(1100, 760)
        self.configure(fg_color="#0c1422")
        position_window_at_top(self)

        panel = CampaignGraphPanel(
            self,
            campaign_wrapper=campaign_wrapper,
            scenario_wrapper=scenario_wrapper,
        )
        panel.pack(fill="both", expand=True)
        self.panel = panel
        self.bind("<Destroy>", self._on_destroy, add="+")

    def _on_destroy(self, _event=None) -> None:
        parent = getattr(self, "master", None)
        if parent is not None and getattr(parent, "_campaign_graph_window", None) is self:
            parent._campaign_graph_window = None
