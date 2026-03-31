"""Dialog for event date agenda."""

from __future__ import annotations

from datetime import date

import customtkinter as ctk

from modules.events.services.campaign_date_service import CampaignDateService
from modules.events.services.date_validation import max_days_for_month, validate_date_parts, validate_iso_text


class CampaignDateAgendaDialog(ctk.CTkToplevel):
    def __init__(self, master, *, initial_date: date | None = None, on_apply=None):
        """Initialize the CampaignDateAgendaDialog instance."""
        super().__init__(master)
        self.title("Set campaign day")
        self.geometry("420x290")
        self.resizable(False, False)

        self._on_apply = on_apply
        self._selected_date = CampaignDateService.get_today()

        self._build_ui()
        self._set_controls_from_date(self._selected_date)
        self._validate_from_parts()

        self.transient(master)
        self.grab_set()
        self.focus_force()

    def _build_ui(self):
        """Build UI."""
        self.grid_columnconfigure(1, weight=1)

        row = 0
        ctk.CTkLabel(self, text="Year").grid(row=row, column=0, padx=14, pady=(16, 8), sticky="w")
        self.year_var = ctk.StringVar(value="")
        self.year_entry = ctk.CTkEntry(self, textvariable=self.year_var)
        self.year_entry.grid(row=row, column=1, padx=(0, 14), pady=(16, 8), sticky="ew")
        self.year_entry.bind("<KeyRelease>", lambda _event: self._validate_from_parts())

        row += 1
        ctk.CTkLabel(self, text="Month").grid(row=row, column=0, padx=14, pady=8, sticky="w")
        month_values = [f"{value:02d}" for value in range(1, 13)]
        self.month_var = ctk.StringVar(value=month_values[0])
        self.month_selector = ctk.CTkOptionMenu(self, values=month_values, variable=self.month_var, command=lambda _v: self._validate_from_parts())
        self.month_selector.grid(row=row, column=1, padx=(0, 14), pady=8, sticky="ew")

        row += 1
        ctk.CTkLabel(self, text="Day").grid(row=row, column=0, padx=14, pady=8, sticky="w")
        self.day_var = ctk.StringVar(value="01")
        self.day_selector = ctk.CTkOptionMenu(self, values=["01"], variable=self.day_var, command=lambda _v: self._validate_from_parts())
        self.day_selector.grid(row=row, column=1, padx=(0, 14), pady=8, sticky="ew")

        row += 1
        ctk.CTkLabel(self, text="Date rapide (YYYY-MM-DD)").grid(row=row, column=0, padx=14, pady=(8, 4), sticky="w")
        self.iso_var = ctk.StringVar(value="")
        self.iso_entry = ctk.CTkEntry(self, textvariable=self.iso_var, placeholder_text="YYYY-MM-DD")
        self.iso_entry.grid(row=row, column=1, padx=(0, 14), pady=(8, 4), sticky="ew")
        self.iso_entry.bind("<KeyRelease>", lambda _event: self._validate_from_text())

        row += 1
        self.feedback_label = ctk.CTkLabel(self, text="", anchor="w")
        self.feedback_label.grid(row=row, column=0, columnspan=2, padx=14, pady=(2, 12), sticky="ew")

        row += 1
        actions = ctk.CTkFrame(self, fg_color="transparent")
        actions.grid(row=row, column=0, columnspan=2, padx=14, pady=(0, 14), sticky="e")
        ctk.CTkButton(actions, text="Cancel", width=90, command=self.destroy).pack(side="left", padx=(0, 8))
        self.apply_button = ctk.CTkButton(actions, text="Apply", width=90, command=self._apply)
        self.apply_button.pack(side="left")

    def _set_controls_from_date(self, value: date):
        """Set controls from date."""
        self.year_var.set(str(value.year))
        self.month_var.set(f"{value.month:02d}")
        self._set_day_options(value.year, value.month, value.day)
        self.iso_var.set(value.isoformat())

    def _set_day_options(self, year: int, month: int, day: int | None = None):
        """Set day options."""
        max_day = max_days_for_month(year, month)
        values = [f"{value:02d}" for value in range(1, max_day + 1)]
        self.day_selector.configure(values=values)

        current_day = day if day is not None else int(self.day_var.get() or 1)
        current_day = max(1, min(max_day, int(current_day)))
        self.day_var.set(f"{current_day:02d}")

    def _validate_from_parts(self):
        """Validate from parts."""
        try:
            year_value = int((self.year_var.get() or "").strip())
        except ValueError:
            self._set_invalid("Invalid year (1-9999).")
            return

        try:
            month_value = int(self.month_var.get())
        except ValueError:
            self._set_invalid("Invalid month (1-12).")
            return

        self._set_day_options(year_value, month_value)

        try:
            day_value = int(self.day_var.get())
        except ValueError:
            self._set_invalid("Invalid day.")
            return

        result = validate_date_parts(year_value, month_value, day_value)
        if result.is_valid:
            self._selected_date = result.date_value
            self.iso_var.set(self._selected_date.isoformat())
            self._set_valid()
            return

        self._set_invalid(result.error_message or "Invalid date.")

    def _validate_from_text(self):
        """Validate from text."""
        result = validate_iso_text(self.iso_var.get())
        if not result.is_valid:
            self._set_invalid(result.error_message or "Invalid date.")
            return

        self._selected_date = result.date_value
        self._set_controls_from_date(self._selected_date)
        self._set_valid()

    def _set_invalid(self, message: str):
        """Set invalid."""
        self.feedback_label.configure(text=message, text_color="#d65a5a")
        self.apply_button.configure(state="disabled")

    def _set_valid(self):
        """Set valid."""
        if self._selected_date is None:
            self._set_invalid("Invalid date.")
            return

        self.feedback_label.configure(text="Valid date.", text_color=("#2e8b57", "#5dd39e"))
        self.apply_button.configure(state="normal")

    def _apply(self):
        """Apply the operation."""
        if self._selected_date is None:
            self._set_invalid("Invalid date.")
            return

        campaign_today = CampaignDateService.set_today(date(self._selected_date.year, self._selected_date.month, self._selected_date.day))
        if callable(self._on_apply):
            self._on_apply(campaign_today)
        self.destroy()


# Backward-compatible alias
DateAgendaDialog = CampaignDateAgendaDialog
