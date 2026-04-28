"""Standalone ambiance control window."""

from __future__ import annotations

import customtkinter as ctk

from modules.scenarios.gm_table.ambiance.page import GMTableAmbiancePage


class AmbianceControlWindow(ctk.CTkToplevel):
    """Top-level standalone window hosting ambiance controls."""

    def __init__(self, master) -> None:
        super().__init__(master)
        self.title("Ambiance Control")
        self.geometry("1320x860")
        self.minsize(980, 620)
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        panel = GMTableAmbiancePage(self)
        panel.grid(row=0, column=0, sticky="nsew")
        self.panel = panel
