import calendar
from datetime import timedelta

import customtkinter as ctk


class CalendarGridPanel(ctk.CTkFrame):
    """Main calendar views: month, week, day and timeline."""

    def __init__(self, master, *, get_events_for_day, on_day_selected):
        super().__init__(master)
        self.get_events_for_day = get_events_for_day
        self._on_day_selected = on_day_selected

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self._month_matrix = []

    @staticmethod
    def _start_of_week(target_date):
        return target_date - timedelta(days=target_date.weekday())

    def render(self, *, view_mode, anchor_date, active_date):
        for child in self.winfo_children():
            child.destroy()

        if view_mode == "month":
            self._render_month(anchor_date, active_date)
        elif view_mode == "week":
            self._render_week(anchor_date, active_date)
        elif view_mode == "timeline":
            self._render_timeline(active_date)
        else:
            self._render_day(active_date)

    def _render_month(self, anchor_date, active_date):
        frame = ctk.CTkFrame(self)
        frame.grid(row=0, column=0, sticky="nsew", padx=6, pady=6)

        for col, label in enumerate(("L", "M", "M", "J", "V", "S", "D")):
            ctk.CTkLabel(frame, text=label).grid(row=0, column=col, padx=2, pady=(4, 2), sticky="ew")

        matrix = calendar.Calendar(firstweekday=0).monthdatescalendar(anchor_date.year, anchor_date.month)
        self._month_matrix = matrix

        for week_idx, week in enumerate(matrix):
            for day_idx, day_date in enumerate(week):
                is_current_month = day_date.month == anchor_date.month
                is_selected = day_date == active_date
                ctk.CTkButton(
                    frame,
                    text=str(day_date.day),
                    width=42,
                    height=34,
                    fg_color=("#2f6cc0", "#2f6cc0") if is_selected else "transparent",
                    text_color=("#1a1a1a", "#f0f0f0") if is_current_month else ("#999999", "#666666"),
                    command=lambda current=day_date: self._emit_day_selected(current),
                ).grid(row=week_idx + 1, column=day_idx, padx=2, pady=2)

    def _render_week(self, anchor_date, active_date):
        frame = ctk.CTkFrame(self)
        frame.grid(row=0, column=0, sticky="nsew", padx=6, pady=6)
        frame.grid_columnconfigure(0, weight=1)

        start = self._start_of_week(anchor_date)
        for offset in range(7):
            day = start + timedelta(days=offset)
            events = self.get_events_for_day(day)
            marker = " •" if events else ""
            label = f"{day.strftime('%A %d/%m')}{marker}".capitalize()
            ctk.CTkButton(
                frame,
                text=label,
                anchor="w",
                fg_color=("#2f6cc0", "#2f6cc0") if day == active_date else "transparent",
                command=lambda current=day: self._emit_day_selected(current),
            ).grid(row=offset, column=0, sticky="ew", padx=6, pady=4)

    def _render_day(self, active_date):
        frame = ctk.CTkFrame(self)
        frame.grid(row=0, column=0, sticky="nsew", padx=6, pady=6)

        events = self.get_events_for_day(active_date)
        ctk.CTkLabel(
            frame,
            text=f"{len(events)} évènement(s) pour {active_date.strftime('%d/%m/%Y')}",
            font=ctk.CTkFont(size=16, weight="bold"),
        ).pack(anchor="w", padx=12, pady=12)

        if not events:
            ctk.CTkLabel(frame, text="Aucun évènement pour cette journée.").pack(anchor="w", padx=12, pady=(0, 12))

    def _render_timeline(self, active_date):
        frame = ctk.CTkScrollableFrame(self)
        frame.grid(row=0, column=0, sticky="nsew", padx=6, pady=6)

        events = self.get_events_for_day(active_date)
        mapped = {str(event.get("time", "")): event for event in events}
        for hour in range(0, 24):
            key = f"{hour:02d}:00"
            event = mapped.get(key)
            title = event.get("title", "Libre") if event else "Libre"
            ctk.CTkButton(
                frame,
                text=f"{key}  —  {title}",
                anchor="w",
                fg_color="transparent",
                command=lambda current=active_date: self._emit_day_selected(current),
            ).pack(fill="x", padx=6, pady=2)

    def _emit_day_selected(self, selected_date):
        if callable(self._on_day_selected):
            self._on_day_selected(selected_date)
