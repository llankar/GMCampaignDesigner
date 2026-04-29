from __future__ import annotations

from dataclasses import dataclass

import customtkinter as ctk


@dataclass(slots=True)
class NodeGeometry:
    node_id: str
    x: float
    y: float
    width: float = 220
    height: float = 100


class NodeFields(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color="transparent")
        self.grid_columnconfigure(0, weight=1)
        self.title_var = ctk.StringVar()
        self.objective_var = ctk.StringVar()
        self.success_condition_var = ctk.StringVar()

        self._entry("Node title", self.title_var, 0)
        self._entry("Objective", self.objective_var, 2)
        self._entry("Success condition", self.success_condition_var, 4)

    def _entry(self, label: str, variable: ctk.StringVar, row: int) -> None:
        ctk.CTkLabel(self, text=label).grid(row=row, column=0, sticky="w", padx=12, pady=(4, 2))
        ctk.CTkEntry(self, textvariable=variable).grid(row=row + 1, column=0, sticky="ew", padx=12)
