"""Popover UI for event quick add."""
from datetime import date, datetime, time, timedelta
from tkinter import colorchooser

import customtkinter as ctk

from modules.events.ui.shared.color_utils import normalize_hex_color
from .event_editor_dialog import EventEditorDialog


class QuickAddPopover(ctk.CTkToplevel):
    """Lightweight quick-create dialog for calendar events."""

    def __init__(self, master, *, initial_date=None, initial_start_time=None, on_create=None, on_more_options=None):
        """Initialize the QuickAddPopover instance."""
        super().__init__(master)
        self.title("Ajout rapide")
        self.geometry("420x360")
        self.resizable(False, False)

        self._on_create = on_create
        self._on_more_options = on_more_options

        self._initial_date = initial_date or date.today()
        self._initial_start_time = self._normalize_time(initial_start_time)

        self._build_ui()
        self._prefill_values()

        self.transient(master)
        self.grab_set()

    def _build_ui(self):
        """Build UI."""
        self.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(self, text="Title").grid(row=0, column=0, padx=12, pady=(16, 8), sticky="w")
        self.title_entry = ctk.CTkEntry(self, placeholder_text="New event")
        self.title_entry.grid(row=0, column=1, padx=12, pady=(16, 8), sticky="ew")

        ctk.CTkLabel(self, text="Date").grid(row=1, column=0, padx=12, pady=8, sticky="w")
        self.date_entry = ctk.CTkEntry(self, placeholder_text="YYYY-MM-DD")
        self.date_entry.grid(row=1, column=1, padx=12, pady=8, sticky="ew")

        ctk.CTkLabel(self, text="Start time").grid(row=2, column=0, padx=12, pady=8, sticky="w")
        self.start_entry = ctk.CTkEntry(self, placeholder_text="HH:MM")
        self.start_entry.grid(row=2, column=1, padx=12, pady=8, sticky="ew")

        ctk.CTkLabel(self, text="End time").grid(row=3, column=0, padx=12, pady=8, sticky="w")
        self.end_entry = ctk.CTkEntry(self, placeholder_text="HH:MM")
        self.end_entry.grid(row=3, column=1, padx=12, pady=8, sticky="ew")

        ctk.CTkLabel(self, text="Type").grid(row=4, column=0, padx=12, pady=8, sticky="w")
        self.type_menu = ctk.CTkOptionMenu(self, values=["Session", "Encounter", "Quest", "Other"])
        self.type_menu.grid(row=4, column=1, padx=12, pady=8, sticky="ew")

        ctk.CTkLabel(self, text="Color").grid(row=5, column=0, padx=12, pady=8, sticky="w")
        self.color_value = "#4F8EF7"
        self.color_button = ctk.CTkButton(self, text="", command=self._choose_color)
        self.color_button.grid(row=5, column=1, padx=12, pady=8, sticky="w")
        self._update_color_button()

        ctk.CTkLabel(self, text="Status").grid(row=6, column=0, padx=12, pady=8, sticky="w")
        self.status_menu = ctk.CTkOptionMenu(self, values=["Planned", "Confirmed", "Completed", "Canceled"])
        self.status_menu.grid(row=6, column=1, padx=12, pady=8, sticky="ew")

        buttons = ctk.CTkFrame(self, fg_color="transparent")
        buttons.grid(row=7, column=0, columnspan=2, padx=12, pady=(16, 12), sticky="e")
        ctk.CTkButton(buttons, text="Plus d'options", fg_color="transparent", command=self._open_more_options).pack(
            side="left", padx=(0, 8)
        )
        ctk.CTkButton(buttons, text="Create", command=self._emit_create).pack(side="right")

    @staticmethod
    def _normalize_time(value):
        """Normalize time."""
        if not value:
            return "09:00"
        if isinstance(value, time):
            return value.strftime("%H:%M")
        if isinstance(value, str):
            # Handle the branch where isinstance(value, str).
            text = value.strip()
            if len(text) == 5 and text[2] == ":":
                return text
            return text[:5]
        return "09:00"

    def _prefill_values(self):
        """Internal helper for prefill values."""
        self.date_entry.insert(0, self._initial_date.isoformat())
        self.start_entry.insert(0, self._initial_start_time)
        self.end_entry.insert(0, self._suggest_end_time(self._initial_start_time))
        self.type_menu.set("Session")
        self.status_menu.set("Planned")

    @staticmethod
    def _suggest_end_time(start_text):
        """Internal helper for suggest end time."""
        try:
            parsed = datetime.strptime(start_text, "%H:%M")
            return (parsed + timedelta(hours=1)).strftime("%H:%M")
        except ValueError:
            return "10:00"

    def _collect_payload(self):
        """Collect payload."""
        return {
            "title": self.title_entry.get().strip(),
            "date": self.date_entry.get().strip(),
            "start_time": self.start_entry.get().strip(),
            "end_time": self.end_entry.get().strip(),
            "type": self.type_menu.get().strip(),
            "color": self.color_value,
            "status": self.status_menu.get().strip(),
        }

    def _emit_create(self):
        """Internal helper for emit create."""
        if callable(self._on_create):
            self._on_create(self._collect_payload())
        self.destroy()

    def _open_more_options(self):
        """Open more options."""
        initial_values = self._collect_payload()

        def _save_from_editor(payload):
            """Save from editor."""
            if callable(self._on_more_options):
                self._on_more_options(payload)
            self.destroy()

        EventEditorDialog(self, initial_values=initial_values, on_save=_save_from_editor)

    def _choose_color(self):
        """Internal helper for choose color."""
        current = normalize_hex_color(self.color_value, fallback="#4F8EF7")
        selection = colorchooser.askcolor(color=current, parent=self)
        color = None
        if isinstance(selection, (tuple, list)) and len(selection) > 1:
            color = selection[1]
        self.color_value = normalize_hex_color(color, fallback=current)
        self._update_color_button()

    def _update_color_button(self):
        """Update color button."""
        self.color_button.configure(
            text=self.color_value,
            fg_color=self.color_value,
            hover_color=self.color_value,
            text_color="#FFFFFF",
        )
