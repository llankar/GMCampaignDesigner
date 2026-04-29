from __future__ import annotations

import customtkinter as ctk


class GraphToolbar(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color="transparent")
        ctk.CTkLabel(self, text="Flow Graph (Wizard + Node Editor)", font=ctk.CTkFont(size=15, weight="bold")).pack(anchor="w")
