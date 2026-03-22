from __future__ import annotations

import customtkinter as ctk


class OutlinedPill(ctk.CTkFrame):
    """Small rounded badge rendered with a frame border for CTk compatibility."""

    def __init__(
        self,
        parent,
        *,
        text: str,
        text_color: str,
        fg_color: str,
        border_color: str,
        padx: int = 10,
        pady: int = 4,
        font=None,
    ):
        super().__init__(
            parent,
            fg_color=fg_color,
            corner_radius=999,
            border_width=1,
            border_color=border_color,
        )
        ctk.CTkLabel(
            self,
            text=text,
            text_color=text_color,
            font=font,
        ).grid(row=0, column=0, padx=padx, pady=pady)
