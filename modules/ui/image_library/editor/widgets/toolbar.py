"""Top toolbar for image editor metadata/actions."""

from __future__ import annotations

import tkinter as tk

import customtkinter as ctk


class EditorToolbar(ctk.CTkFrame):
    """Path/header strip displayed above the editor workspace."""

    def __init__(self, master: tk.Misc, *, source_path: str) -> None:
        super().__init__(master)
        self.grid_columnconfigure(0, weight=1)
        self._path_label = ctk.CTkLabel(self, text=source_path, anchor="w")
        self._path_label.grid(row=0, column=0, sticky="ew", padx=10, pady=8)

    def set_source_path(self, source_path: str) -> None:
        self._path_label.configure(text=source_path)
