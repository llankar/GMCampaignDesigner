import calendar
from datetime import date, timedelta

import customtkinter as ctk


class CalendarWindow(ctk.CTkToplevel):
    """Dedicated full calendar window supporting month/week/day navigation."""

    VIEW_MONTH = "month"
    VIEW_WEEK = "week"
    VIEW_DAY = "day"
    SUPPORTED_VIEWS = {VIEW_MONTH, VIEW_WEEK, VIEW_DAY}

    def __init__(
        self,
        master,
        get_events_for_day,
        get_events_for_range,
        initial_date=None,
        initial_view_mode="month",
        on_state_change=None,
    ):
        super().__init__(master)
        self.title("Calendrier complet")
        self.geometry("1100x760")

        self.get_events_for_day = get_events_for_day
        self.get_events_for_range = get_events_for_range
        self.on_state_change = on_state_change

        self.active_date = initial_date or date.today()
        self.view_mode = self._normalize_view_mode(initial_view_mode)
        self.anchor_date = self.active_date

        self._month_buttons = []
        self._month_cell_dates = []
        self._week_day_buttons = []

        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._close_window)
        self._render()

    @classmethod
    def _normalize_view_mode(cls, mode):
        normalized = str(mode or "").lower().strip()
        if normalized in cls.SUPPORTED_VIEWS:
            return normalized
        return cls.VIEW_MONTH

    @staticmethod
    def _start_of_week(target_date):
        return target_date - timedelta(days=target_date.weekday())

    def _build_ui(self):
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        toolbar = ctk.CTkFrame(self)
        toolbar.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 6))
        toolbar.grid_columnconfigure(1, weight=1)

        nav = ctk.CTkFrame(toolbar, fg_color="transparent")
        nav.grid(row=0, column=0, sticky="w")

        ctk.CTkButton(nav, text="◀", width=34, command=self._go_previous).pack(side="left", padx=(0, 6))
        ctk.CTkButton(nav, text="Aujourd'hui", width=90, command=self._jump_today).pack(side="left", padx=(0, 6))
        ctk.CTkButton(nav, text="▶", width=34, command=self._go_next).pack(side="left")

        self.period_label = ctk.CTkLabel(toolbar, text="", font=ctk.CTkFont(size=15, weight="bold"))
        self.period_label.grid(row=0, column=1, sticky="w", padx=(8, 8))

        self.view_mode_switch = ctk.CTkSegmentedButton(
            toolbar,
            values=["Mois", "Semaine", "Jour"],
            command=self._on_mode_switch,
            width=260,
        )
        self.view_mode_switch.grid(row=0, column=2, sticky="e")

        content = ctk.CTkFrame(self)
        content.grid(row=1, column=0, sticky="nsew", padx=12, pady=(6, 12))
        content.grid_rowconfigure(0, weight=1)
        content.grid_columnconfigure(0, weight=3)
        content.grid_columnconfigure(1, weight=2)

        self.primary_frame = ctk.CTkFrame(content)
        self.primary_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        self.primary_frame.grid_rowconfigure(0, weight=1)
        self.primary_frame.grid_columnconfigure(0, weight=1)

        details_frame = ctk.CTkFrame(content)
        details_frame.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        details_frame.grid_rowconfigure(1, weight=1)
        details_frame.grid_columnconfigure(0, weight=1)

        self.selection_label = ctk.CTkLabel(
            details_frame,
            text="",
            anchor="w",
            font=ctk.CTkFont(size=14, weight="bold"),
        )
        self.selection_label.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 6))

        self.events_text = ctk.CTkTextbox(details_frame)
        self.events_text.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self.events_text.configure(state="disabled")

    def _on_mode_switch(self, value):
        mapping = {"Mois": self.VIEW_MONTH, "Semaine": self.VIEW_WEEK, "Jour": self.VIEW_DAY}
        self.set_view_mode(mapping.get(value, self.VIEW_MONTH))

    def _go_previous(self):
        if self.view_mode == self.VIEW_MONTH:
            year, month = self.anchor_date.year, self.anchor_date.month
            if month == 1:
                year, month = year - 1, 12
            else:
                month -= 1
            self.anchor_date = date(year, month, 1)
            self.active_date = self.anchor_date
        elif self.view_mode == self.VIEW_WEEK:
            self.anchor_date -= timedelta(days=7)
            self.active_date = self.anchor_date
        else:
            self.anchor_date -= timedelta(days=1)
            self.active_date = self.anchor_date

        self._render()
        self._emit_state_change()

    def _go_next(self):
        if self.view_mode == self.VIEW_MONTH:
            year, month = self.anchor_date.year, self.anchor_date.month
            if month == 12:
                year, month = year + 1, 1
            else:
                month += 1
            self.anchor_date = date(year, month, 1)
            self.active_date = self.anchor_date
        elif self.view_mode == self.VIEW_WEEK:
            self.anchor_date += timedelta(days=7)
            self.active_date = self.anchor_date
        else:
            self.anchor_date += timedelta(days=1)
            self.active_date = self.anchor_date

        self._render()
        self._emit_state_change()

    def _jump_today(self):
        self.focus_date(date.today(), view_mode=self.view_mode, auto_select=True)

    def set_view_mode(self, view_mode):
        normalized = self._normalize_view_mode(view_mode)
        if normalized == self.view_mode:
            return
        self.view_mode = normalized
        self.anchor_date = self.active_date
        self._render()
        self._emit_state_change()

    def focus_date(self, target_date, view_mode=None, auto_select=True):
        if target_date is None:
            target_date = date.today()
        if view_mode is not None:
            self.view_mode = self._normalize_view_mode(view_mode)

        self.anchor_date = target_date
        if auto_select:
            self.active_date = target_date

        self._render()
        self._emit_state_change()

    def _render(self):
        self._render_view_mode_switch()

        for child in self.primary_frame.winfo_children():
            child.destroy()

        if self.view_mode == self.VIEW_MONTH:
            self._render_month_view()
        elif self.view_mode == self.VIEW_WEEK:
            self._render_week_view()
        else:
            self._render_day_view()

        self._render_event_details()

    def _render_view_mode_switch(self):
        mapping = {
            self.VIEW_MONTH: "Mois",
            self.VIEW_WEEK: "Semaine",
            self.VIEW_DAY: "Jour",
        }
        self.view_mode_switch.set(mapping[self.view_mode])

    def _render_month_view(self):
        self.period_label.configure(text=self.anchor_date.strftime("%B %Y").capitalize())

        frame = ctk.CTkFrame(self.primary_frame)
        frame.grid(row=0, column=0, sticky="nsew", padx=6, pady=6)

        for col, label in enumerate(("L", "M", "M", "J", "V", "S", "D")):
            ctk.CTkLabel(frame, text=label).grid(row=0, column=col, padx=2, pady=(4, 2), sticky="ew")

        matrix = calendar.Calendar(firstweekday=0).monthdatescalendar(self.anchor_date.year, self.anchor_date.month)
        self._month_cell_dates = matrix
        self._month_buttons = []

        for week_index, week in enumerate(matrix):
            row_buttons = []
            for day_index, day_date in enumerate(week):
                is_current_month = day_date.month == self.anchor_date.month
                is_selected = day_date == self.active_date
                button = ctk.CTkButton(
                    frame,
                    text=str(day_date.day),
                    width=42,
                    height=34,
                    fg_color=("#2f6cc0", "#2f6cc0") if is_selected else "transparent",
                    text_color=("#1a1a1a", "#f0f0f0") if is_current_month else ("#999999", "#666666"),
                    command=lambda w=week_index, d=day_index: self._select_month_cell(w, d),
                )
                button.grid(row=week_index + 1, column=day_index, padx=2, pady=2)
                row_buttons.append(button)
            self._month_buttons.append(row_buttons)

    def _render_week_view(self):
        start = self._start_of_week(self.anchor_date)
        end = start + timedelta(days=6)
        self.period_label.configure(text=f"Semaine du {start.strftime('%d/%m/%Y')} au {end.strftime('%d/%m/%Y')}")

        frame = ctk.CTkFrame(self.primary_frame)
        frame.grid(row=0, column=0, sticky="nsew", padx=6, pady=6)
        frame.grid_columnconfigure(0, weight=1)

        self._week_day_buttons = []
        for offset in range(7):
            day = start + timedelta(days=offset)
            events = self.get_events_for_day(day)
            marker = " •" if events else ""
            label = f"{day.strftime('%A %d/%m')}{marker}".capitalize()
            btn = ctk.CTkButton(
                frame,
                text=label,
                anchor="w",
                fg_color=("#2f6cc0", "#2f6cc0") if day == self.active_date else "transparent",
                command=lambda current=day: self._select_day(current),
            )
            btn.grid(row=offset, column=0, sticky="ew", padx=6, pady=4)
            self._week_day_buttons.append(btn)

    def _render_day_view(self):
        self.period_label.configure(text=self.anchor_date.strftime("%A %d %B %Y").capitalize())

        frame = ctk.CTkFrame(self.primary_frame)
        frame.grid(row=0, column=0, sticky="nsew", padx=6, pady=6)

        events = self.get_events_for_day(self.active_date)
        ctk.CTkLabel(
            frame,
            text=f"{len(events)} évènement(s) pour {self.active_date.strftime('%d/%m/%Y')}",
            font=ctk.CTkFont(size=16, weight="bold"),
        ).pack(anchor="w", padx=12, pady=12)

        if not events:
            ctk.CTkLabel(frame, text="Aucun évènement pour cette journée.").pack(anchor="w", padx=12, pady=(0, 12))

    def _select_month_cell(self, week_index, day_index):
        self._select_day(self._month_cell_dates[week_index][day_index])

    def _select_day(self, selected_date):
        self.active_date = selected_date
        self.anchor_date = selected_date
        self._render()
        self._emit_state_change()

    def _render_event_details(self):
        self.selection_label.configure(text=f"Jour sélectionné : {self.active_date.strftime('%A %d/%m/%Y').capitalize()}")
        events = self.get_events_for_day(self.active_date)
        lines = self._format_event_lines(events)
        self._set_textbox_lines(self.events_text, lines)

    def _close_window(self):
        self.withdraw()

    def _emit_state_change(self):
        if callable(self.on_state_change):
            self.on_state_change(self.active_date, self.view_mode)

    @staticmethod
    def _format_event_lines(events):
        if not events:
            return ["Aucun évènement."]

        lines = []
        for event in events:
            title = event.get("title", "Sans titre")
            source = event.get("source")
            if source:
                lines.append(f"• {title} ({source})")
            else:
                lines.append(f"• {title}")
        return lines

    @staticmethod
    def _set_textbox_lines(textbox, lines):
        textbox.configure(state="normal")
        textbox.delete("1.0", "end")
        textbox.insert("1.0", "\n".join(lines))
        textbox.configure(state="disabled")
