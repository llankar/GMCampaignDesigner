"""Section definitions for event editor."""
from __future__ import annotations

import customtkinter as ctk

from .palette import get_event_editor_palette


class EventEditorSection(ctk.CTkFrame):
    """Card-like section used by the calendar event editor."""

    def __init__(self, master, *, title: str, description: str = ""):
        """Initialize the EventEditorSection instance."""
        self._palette = get_event_editor_palette()
        super().__init__(
            master,
            fg_color=self._palette.panel_bg,
            corner_radius=18,
            border_width=1,
            border_color=self._palette.border,
        )
        self.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            self,
            text=title,
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=self._palette.text_primary,
        ).grid(row=0, column=0, padx=18, pady=(16, 2), sticky="w")

        if description:
            ctk.CTkLabel(
                self,
                text=description,
                text_color=self._palette.text_secondary,
                justify="left",
                wraplength=780,
            ).grid(row=1, column=0, padx=18, pady=(0, 12), sticky="w")
            content_row = 2
        else:
            content_row = 1

        self.content = ctk.CTkFrame(self, fg_color="transparent")
        self.content.grid(row=content_row, column=0, padx=18, pady=(0, 18), sticky="nsew")
        self.content.grid_columnconfigure(0, weight=1)


class EventEditorHero(ctk.CTkFrame):
    """Top summary block with a live snapshot of the event state."""

    def __init__(self, master):
        """Initialize the EventEditorHero instance."""
        self._palette = get_event_editor_palette()
        super().__init__(
            master,
            fg_color=self._palette.panel_alt_bg,
            corner_radius=22,
            border_width=1,
            border_color=self._palette.border,
        )
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0)

        self.eyebrow_label = ctk.CTkLabel(
            self,
            text="Calendar event",
            text_color=self._palette.text_secondary,
            font=ctk.CTkFont(size=13, weight="bold"),
        )
        self.eyebrow_label.grid(row=0, column=0, padx=20, pady=(18, 2), sticky="w")

        self.title_label = ctk.CTkLabel(
            self,
            text="Create a polished event",
            text_color=self._palette.text_primary,
            font=ctk.CTkFont(size=28, weight="bold"),
        )
        self.title_label.grid(row=1, column=0, padx=20, pady=(0, 6), sticky="w")

        self.subtitle_label = ctk.CTkLabel(
            self,
            text="Organize timing, tone, and campaign links from one focused workspace.",
            text_color=self._palette.text_secondary,
            justify="left",
            wraplength=560,
        )
        self.subtitle_label.grid(row=2, column=0, padx=20, pady=(0, 16), sticky="w")

        chips = ctk.CTkFrame(self, fg_color="transparent")
        chips.grid(row=3, column=0, padx=20, pady=(0, 18), sticky="w")

        self.type_chip = self._build_chip(chips, 0)
        self.schedule_chip = self._build_chip(chips, 1)
        self.status_chip = self._build_chip(chips, 2)

        self.color_swatch = ctk.CTkFrame(
            self,
            width=88,
            height=88,
            corner_radius=24,
            fg_color=self._palette.accent,
            border_width=1,
            border_color=self._palette.border,
        )
        self.color_swatch.grid(row=0, column=1, rowspan=4, padx=(12, 20), pady=18, sticky="e")
        self.color_swatch.grid_propagate(False)

        self.color_code_label = ctk.CTkLabel(
            self.color_swatch,
            text="#4F8EF7",
            text_color="#FFFFFF",
            font=ctk.CTkFont(size=13, weight="bold"),
        )
        self.color_code_label.place(relx=0.5, rely=0.5, anchor="center")

    def _build_chip(self, master, column: int):
        """Build chip."""
        chip = ctk.CTkLabel(
            master,
            text="",
            fg_color=self._palette.muted_chip,
            corner_radius=999,
            text_color=self._palette.text_primary,
            padx=12,
            pady=6,
        )
        chip.grid(row=0, column=column, padx=(0, 8), sticky="w")
        return chip

    def update_preview(self, *, title: str, event_type: str, schedule: str, status: str, color: str):
        """Update preview."""
        display_title = (title or "Untitled event").strip() or "Untitled event"
        self.title_label.configure(text=display_title)
        self.type_chip.configure(text=f"Type · {event_type or 'Session'}")
        self.schedule_chip.configure(text=f"Schedule · {schedule or 'Date to define'}")
        self.status_chip.configure(text=f"Status · {status or 'Draft'}")
        self.color_swatch.configure(fg_color=color)
        self.color_code_label.configure(text=color)
