from __future__ import annotations

import customtkinter as ctk

from modules.campaigns.ui.theme import ARC_EDITOR_PALETTE


class FormSection(ctk.CTkFrame):
    """Reusable card section with title and optional helper copy."""

    def __init__(self, master, *, title: str, description: str | None = None):
        super().__init__(
            master,
            fg_color=ARC_EDITOR_PALETTE.surface,
            corner_radius=18,
            border_width=1,
            border_color=ARC_EDITOR_PALETTE.border,
        )
        self.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            self,
            text=title,
            anchor="w",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=ARC_EDITOR_PALETTE.text_primary,
        ).grid(row=0, column=0, sticky="ew", padx=18, pady=(16, 2))

        if description:
            ctk.CTkLabel(
                self,
                text=description,
                anchor="w",
                justify="left",
                wraplength=620,
                text_color=ARC_EDITOR_PALETTE.text_secondary,
            ).grid(row=1, column=0, sticky="ew", padx=18, pady=(0, 12))
            self.content_row = 2
        else:
            self.content_row = 1

        self.body = ctk.CTkFrame(self, fg_color="transparent")
        self.body.grid(row=self.content_row, column=0, sticky="nsew", padx=18, pady=(0, 18))
        self.body.grid_columnconfigure(0, weight=1)
