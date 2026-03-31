"""Dialog for event timeline simulator."""

from datetime import date, timedelta
from tkinter import messagebox

import customtkinter as ctk

from modules.events.services.timeline_simulator import TimelineSimulationResult
from modules.events.ui.shared.schedule_widgets import EventDatePickerField, parse_event_date
from modules.helpers.window_helper import position_window_at_top


def format_timeline_result_summary(result: TimelineSimulationResult) -> str:
    """Format timeline result summary."""
    lines = [
        f"Timeline advanced from {result.start_date.isoformat()} to {result.end_date.isoformat()}.",
        f"Days advanced: {result.days_advanced}",
        f"Resolved events: {result.resolved_events}",
        f"Faction escalations: {result.escalated_factions}",
        f"Villain escalations: {result.escalated_villains}",
        f"Base projects advanced: {result.advanced_projects}",
        f"NPC movements: {result.npc_movements}",
        f"Total changes: {result.change_count}",
        "",
        result.gm_summary,
    ]
    return "\n".join(lines).strip()


class TimelineSimulatorDialog(ctk.CTkToplevel):
    MODE_TARGET_DATE = "Target date"
    MODE_ADVANCE_DAYS = "Advance days"

    def __init__(
        self,
        master,
        *,
        current_date: date,
        initial_target_date: date | None = None,
        on_run=None,
    ):
        """Initialize the TimelineSimulatorDialog instance."""
        super().__init__(master)
        self.title("Advance Timeline")
        self.geometry("620x720")
        self.resizable(True, True)

        self._on_run = on_run
        self._current_date = current_date
        self._mode = self.MODE_TARGET_DATE

        self._build_ui(initial_target_date or current_date)
        self._refresh_current_date_label()
        self._refresh_preview()

        self.transient(master)
        self.grab_set()
        position_window_at_top(self)

    def _build_ui(self, initial_target_date: date):
        """Build UI."""
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        header = ctk.CTkFrame(self)
        header.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 8))
        header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            header,
            text="Advance campaign time and apply scheduled world-state changes.",
            anchor="w",
            justify="left",
        ).grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 4))
        self.current_date_label = ctk.CTkLabel(header, text="", anchor="w")
        self.current_date_label.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 12))

        body = ctk.CTkScrollableFrame(self)
        body.grid(row=1, column=0, sticky="nsew", padx=12, pady=0)
        body.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(body, text="Mode", anchor="w").grid(row=0, column=0, sticky="w", padx=8, pady=(8, 4))
        self.mode_switch = ctk.CTkSegmentedButton(
            body,
            values=[self.MODE_TARGET_DATE, self.MODE_ADVANCE_DAYS],
            command=self._on_mode_changed,
        )
        self.mode_switch.grid(row=1, column=0, sticky="ew", padx=8, pady=(0, 10))
        self.mode_switch.set(self.MODE_TARGET_DATE)

        self.target_date_frame = ctk.CTkFrame(body)
        self.target_date_frame.grid(row=2, column=0, sticky="ew", padx=8, pady=(0, 10))
        self.target_date_frame.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(self.target_date_frame, text="Advance to date", anchor="w").grid(
            row=0, column=0, sticky="w", padx=10, pady=(10, 4)
        )
        self.target_date_picker = EventDatePickerField(
            self.target_date_frame,
            initial_value=initial_target_date,
            picker_button_text="Calendar",
            today_button_text="Today",
            clear_button_text="Clear",
        )
        self.target_date_picker.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 10))
        self.target_date_picker.entry.bind("<KeyRelease>", lambda _e: self._refresh_preview())
        self.target_date_picker.entry.bind("<FocusOut>", lambda _e: self._refresh_preview(), add="+")

        self.days_frame = ctk.CTkFrame(body)
        self.days_frame.grid(row=3, column=0, sticky="ew", padx=8, pady=(0, 10))
        self.days_frame.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(self.days_frame, text="Advance by number of days", anchor="w").grid(
            row=0, column=0, sticky="w", padx=10, pady=(10, 4)
        )
        self.days_entry = ctk.CTkEntry(self.days_frame, placeholder_text="e.g. 7")
        self.days_entry.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 8))
        self.days_entry.insert(0, "1")
        self.days_entry.bind("<KeyRelease>", lambda _e: self._refresh_preview())
        self.days_entry.bind("<FocusOut>", lambda _e: self._refresh_preview(), add="+")

        quick_days = ctk.CTkFrame(self.days_frame, fg_color="transparent")
        quick_days.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 10))
        for value in (1, 3, 7, 30):
            ctk.CTkButton(
                quick_days,
                text=f"+{value}",
                width=64,
                command=lambda amount=value: self._set_days(amount),
            ).pack(side="left", padx=(0, 6))

        self.preview_frame = ctk.CTkFrame(body)
        self.preview_frame.grid(row=4, column=0, sticky="ew", padx=8, pady=(0, 10))
        self.preview_frame.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(self.preview_frame, text="Preview", anchor="w").grid(
            row=0, column=0, sticky="w", padx=10, pady=(10, 4)
        )
        self.preview_label = ctk.CTkLabel(self.preview_frame, text="", anchor="w", justify="left")
        self.preview_label.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 10))

        self.summary_frame = ctk.CTkFrame(body)
        self.summary_frame.grid(row=5, column=0, sticky="nsew", padx=8, pady=(0, 12))
        self.summary_frame.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(self.summary_frame, text="Latest simulation result", anchor="w").grid(
            row=0, column=0, sticky="w", padx=10, pady=(10, 4)
        )
        self.summary_text = ctk.CTkTextbox(self.summary_frame, height=260, wrap="word")
        self.summary_text.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self.summary_text.insert("1.0", "No simulation has been run yet.")
        self.summary_text.configure(state="disabled")

        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.grid(row=2, column=0, sticky="ew", padx=12, pady=(8, 12))
        ctk.CTkButton(footer, text="Close", fg_color="transparent", command=self.destroy).pack(side="right")
        ctk.CTkButton(footer, text="Run Simulation", command=self._run_simulation).pack(side="right", padx=(0, 8))

        self._update_mode_visibility()

    def _refresh_current_date_label(self):
        """Refresh current date label."""
        self.current_date_label.configure(text=f"Current campaign date: {self._current_date.isoformat()}")

    def _on_mode_changed(self, selected_mode):
        """Handle mode changed."""
        self._mode = selected_mode or self.MODE_TARGET_DATE
        self._update_mode_visibility()
        self._refresh_preview()

    def _update_mode_visibility(self):
        """Update mode visibility."""
        if self._mode == self.MODE_ADVANCE_DAYS:
            self.target_date_frame.grid_remove()
            self.days_frame.grid()
        else:
            self.days_frame.grid_remove()
            self.target_date_frame.grid()

    def _set_days(self, amount: int):
        """Set days."""
        self.days_entry.delete(0, "end")
        self.days_entry.insert(0, str(max(0, int(amount))))
        self._refresh_preview()

    def _resolve_target_date(self):
        """Resolve target date."""
        if self._mode == self.MODE_ADVANCE_DAYS:
            # Handle the branch where _mode == MODE_ADVANCE_DAYS.
            raw_days = self.days_entry.get().strip()
            if not raw_days:
                raise ValueError("Enter the number of days to advance.")
            days = int(raw_days)
            if days < 0:
                raise ValueError("The number of days cannot be negative.")
            return self._current_date + timedelta(days=days)

        resolved = parse_event_date(self.target_date_picker.get())
        if resolved is None:
            raise ValueError("Choose a valid target date.")
        return resolved

    def _refresh_preview(self):
        """Refresh preview."""
        try:
            target_date = self._resolve_target_date()
        except Exception as exc:
            self.preview_label.configure(text=f"Pending input: {exc}")
            return

        delta = (target_date - self._current_date).days
        if delta < 0:
            text = (
                f"Invalid range.\n"
                f"Target date {target_date.isoformat()} is before the current campaign date."
            )
        elif delta == 0:
            text = f"The simulator will re-run the campaign state for {target_date.isoformat()} without advancing days."
        else:
            text = (
                f"The campaign will advance from {self._current_date.isoformat()} to {target_date.isoformat()}.\n"
                f"Days advanced: {delta}"
            )
        self.preview_label.configure(text=text)

    def _set_summary(self, text: str):
        """Set summary."""
        self.summary_text.configure(state="normal")
        self.summary_text.delete("1.0", "end")
        self.summary_text.insert("1.0", text)
        self.summary_text.configure(state="disabled")

    def _run_simulation(self):
        """Run simulation."""
        if not callable(self._on_run):
            return

        try:
            target_date = self._resolve_target_date()
        except Exception as exc:
            messagebox.showerror("Timeline Simulator", str(exc), parent=self)
            return

        try:
            result = self._on_run(target_date=target_date)
        except Exception as exc:
            messagebox.showerror("Timeline Simulator", str(exc), parent=self)
            return

        if not isinstance(result, TimelineSimulationResult):
            messagebox.showerror("Timeline Simulator", "Unexpected simulation result.", parent=self)
            return

        self._current_date = result.end_date
        self._refresh_current_date_label()
        self.target_date_picker.set(result.end_date)
        self._refresh_preview()
        self._set_summary(format_timeline_result_summary(result))
