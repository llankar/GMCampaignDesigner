from __future__ import annotations

import customtkinter as ctk

from .node_widgets import NodeFields


class PropertiesPanel(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color="#101827", corner_radius=12)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)

        ctk.CTkLabel(self, text="Properties", font=ctk.CTkFont(size=14, weight="bold")).grid(
            row=0, column=0, sticky="w", padx=12, pady=(10, 6)
        )
        self.fields = NodeFields(self)
        self.fields.grid(row=1, column=0, sticky="ew")

        ctk.CTkLabel(self, text="Notes").grid(row=2, column=0, sticky="w", padx=12, pady=(10, 2))
        self.notes_box = ctk.CTkTextbox(self, height=180)
        self.notes_box.grid(row=3, column=0, sticky="nsew", padx=12, pady=(0, 12))
