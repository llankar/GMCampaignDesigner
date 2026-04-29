from __future__ import annotations

import customtkinter as ctk


class GraphCanvasView(ctk.CTkTextbox):
    """Read-only textual graph canvas placeholder."""

    def __init__(self, master):
        super().__init__(master, corner_radius=12)
