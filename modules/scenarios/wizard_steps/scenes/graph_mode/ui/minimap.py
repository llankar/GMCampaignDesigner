from __future__ import annotations

import customtkinter as ctk


class Minimap(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color="transparent")
