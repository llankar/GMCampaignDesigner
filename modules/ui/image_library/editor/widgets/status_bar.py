"""Status bar for image editor feedback."""

from __future__ import annotations

import tkinter as tk

import customtkinter as ctk


class StatusBar(ctk.CTkFrame):
    """Tiny status bar used for contextual editor messages."""

    def __init__(self, master: tk.Misc) -> None:
        super().__init__(master)
        self.grid_columnconfigure(0, weight=1)
        self._label = ctk.CTkLabel(self, text="Ready", anchor="w")
        self._label.grid(row=0, column=0, sticky="ew", padx=10, pady=6)

    def set_message(self, message: str) -> None:
        self._label.configure(text=message)
