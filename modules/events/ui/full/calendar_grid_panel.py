"""Panel for event calendar grid."""

import calendar
from datetime import timedelta

import customtkinter as ctk

from modules.events.models.event_types import get_event_type


class CalendarGridPanel(ctk.CTkFrame):
    """Main calendar views: month, week, day, agenda and timeline."""

    def __init__(
        self,
        master,
        *,
        get_events_for_day,
        get_events_for_range,
        on_day_selected,
        on_cell_click=None,
        on_cell_double_click=None,
        on_event_moved=None,
        on_event_click=None,
    ):
        """Initialize the CalendarGridPanel instance."""
        super().__init__(master)
        self.get_events_for_day = get_events_for_day
        self.get_events_for_range = get_events_for_range
        self._on_day_selected = on_day_selected
        self._on_cell_click = on_cell_click
        self._on_cell_double_click = on_cell_double_click
        self._on_event_moved = on_event_moved
        self._on_event_click = on_event_click

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self._month_matrix = []
        self._dragged_event = None

    @staticmethod
    def _start_of_week(target_date):
        """Start of week."""
        return target_date - timedelta(days=target_date.weekday())

    def render(self, *, view_mode, anchor_date, active_date, filters=None, filter_predicate=None):
        """Render the operation."""
        for child in self.winfo_children():
            child.destroy()

        predicate = filter_predicate if callable(filter_predicate) else (lambda _event: True)

        if view_mode == "month":
            self._render_month(anchor_date, active_date, predicate)
        elif view_mode == "week":
            self._render_week(anchor_date, active_date, predicate)
        elif view_mode == "timeline":
            self._render_timeline(active_date, predicate)
        elif view_mode == "agenda":
            self._render_agenda(active_date, filters or {}, predicate)
        else:
            self._render_day(active_date, predicate)

    def _render_month(self, anchor_date, active_date, filter_predicate):
        """Render month."""
        frame = ctk.CTkFrame(self)
        frame.grid(row=0, column=0, sticky="nsew", padx=6, pady=6)

        for col, label in enumerate(("L", "M", "M", "J", "V", "S", "D")):
            ctk.CTkLabel(frame, text=label).grid(row=0, column=col, padx=2, pady=(4, 2), sticky="ew")

        matrix = calendar.Calendar(firstweekday=0).monthdatescalendar(anchor_date.year, anchor_date.month)
        self._month_matrix = matrix

        for week_idx, week in enumerate(matrix):
            for day_idx, day_date in enumerate(week):
                # Process each (day_idx, day_date) from enumerate(week).
                is_current_month = day_date.month == anchor_date.month
                is_selected = day_date == active_date
                day_events = [event for event in self.get_events_for_day(day_date) if filter_predicate(event)]
                marker = " •" if day_events else ""
                first_color = self._day_color(day_events)
                button = ctk.CTkButton(
                    frame,
                    text=f"{day_date.day}{marker}",
                    width=42,
                    height=34,
                    fg_color=("#2f6cc0", "#2f6cc0") if is_selected else first_color,
                    text_color=("#1a1a1a", "#f0f0f0") if is_current_month else ("#999999", "#666666"),
                    command=lambda current=day_date: self._emit_cell_click(current),
                )
                button.grid(row=week_idx + 1, column=day_idx, padx=2, pady=2)
                button.bind("<Double-Button-1>", lambda _event, current=day_date: self._emit_cell_double_click(current))
                button.bind("<ButtonRelease-1>", lambda _event, current=day_date: self._drop_event_on_day(current))

    def _render_week(self, anchor_date, active_date, filter_predicate):
        """Render week."""
        frame = ctk.CTkFrame(self)
        frame.grid(row=0, column=0, sticky="nsew", padx=6, pady=6)
        frame.grid_columnconfigure(0, weight=1)

        start = self._start_of_week(anchor_date)
        for offset in range(7):
            # Process each offset from range(7).
            day = start + timedelta(days=offset)
            events = [event for event in self.get_events_for_day(day) if filter_predicate(event)]
            marker = " •" if events else ""
            label = f"{day.strftime('%A %d/%m')}{marker}".capitalize()
            first_color = self._day_color(events)
            button = ctk.CTkButton(
                frame,
                text=label,
                anchor="w",
                fg_color=("#2f6cc0", "#2f6cc0") if day == active_date else first_color,
                command=lambda current=day: self._emit_cell_click(current),
            )
            button.grid(row=offset, column=0, sticky="ew", padx=6, pady=4)
            button.bind("<Double-Button-1>", lambda _event, current=day: self._emit_cell_double_click(current))
            button.bind("<ButtonRelease-1>", lambda _event, current=day: self._drop_event_on_day(current))

    def _render_day(self, active_date, filter_predicate):
        """Render day."""
        frame = ctk.CTkFrame(self)
        frame.grid(row=0, column=0, sticky="nsew", padx=6, pady=6)

        events = [event for event in self.get_events_for_day(active_date) if filter_predicate(event)]
        ctk.CTkLabel(
            frame,
            text=f"{len(events)} event(s) for {active_date.strftime('%d/%m/%Y')}",
            font=ctk.CTkFont(size=16, weight="bold"),
        ).pack(anchor="w", padx=12, pady=12)

        if not events:
            ctk.CTkLabel(frame, text="No events for this day.").pack(anchor="w", padx=12, pady=(0, 12))
            return

        for event in events:
            self._render_event_chip(frame, event)

    def _render_timeline(self, active_date, filter_predicate):
        """Render timeline."""
        frame = ctk.CTkScrollableFrame(self)
        frame.grid(row=0, column=0, sticky="nsew", padx=6, pady=6)

        events = [event for event in self.get_events_for_day(active_date) if filter_predicate(event)]
        mapped = {str(event.get("time", "")): event for event in events}
        for hour in range(0, 24):
            # Process each hour from range(0, 24).
            key = f"{hour:02d}:00"
            event = mapped.get(key)
            title = event.get("title", "Free") if event else "Free"
            slot_color = self._day_color([event] if event else [])
            button = ctk.CTkButton(
                frame,
                text=f"{key}  —  {title}",
                anchor="w",
                fg_color=slot_color,
                text_color=(event.get("color") if event else None) or ("#1a1a1a", "#f0f0f0"),
                command=lambda current=active_date, start=key: self._emit_cell_click(current, start),
            )
            button.pack(fill="x", padx=6, pady=2)
            button.bind("<Double-Button-1>", lambda _event, current=active_date, start_time=key: self._emit_cell_double_click(current, start_time))
            button.bind("<ButtonRelease-1>", lambda _event, current=active_date, start_time=key: self._drop_event_on_day(current, start_time))

    def _render_agenda(self, active_date, filters, filter_predicate):
        """Render agenda."""
        frame = ctk.CTkScrollableFrame(self)
        frame.grid(row=0, column=0, sticky="nsew", padx=6, pady=6)

        window_days = int(filters.get("agenda_window_days") or 7)
        start = active_date
        end = active_date + timedelta(days=max(1, window_days) - 1)
        events = [event for event in self.get_events_for_range(start, end) if filter_predicate(event)]

        ctk.CTkLabel(
            frame,
            text=f"Agenda: {start.strftime('%d/%m')} → {end.strftime('%d/%m')} ({len(events)} event(s))",
            font=ctk.CTkFont(size=15, weight="bold"),
            anchor="w",
        ).pack(fill="x", padx=8, pady=(6, 8))

        if not events:
            ctk.CTkLabel(frame, text="No events in this range.", anchor="w").pack(fill="x", padx=8, pady=6)
            return

        for event in sorted(events, key=lambda row: (row.get("date"), row.get("time") or "", row.get("title") or "")):
            self._render_event_chip(frame, event, include_date=True)

    def _render_event_chip(self, frame, event, include_date=False):
        """Render event chip."""
        event_type = get_event_type(event.get("type"))
        event_date = event.get("date")
        date_prefix = f"[{event_date.strftime('%d/%m')}] " if include_date and event_date else ""
        badge = self._timeline_badge(event)
        details = " / ".join(part for part in [event.get("time") or "", event.get("status") or ""] if part)
        text = f"{date_prefix}{event.get('title', 'Untitled')}"
        if details:
            text = f"{text} — {details}"
        text = f"{text} [{badge}]"

        block = ctk.CTkFrame(frame)
        block.pack(fill="x", padx=8, pady=4)
        label = ctk.CTkLabel(
            block,
            text=text,
            anchor="w",
            justify="left",
            cursor="hand2",
            text_color=event.get("color") or event_type.color,
        )
        label.pack(fill="x", padx=8, pady=6)
        label.bind("<ButtonPress-1>", lambda _event, current=event: self._emit_event_click(current))

    def _start_drag(self, event):
        """Start drag."""
        self._dragged_event = event

    def _drop_event_on_day(self, target_date, target_time=None):
        """Internal helper for drop event on day."""
        if not self._dragged_event:
            return
        moving = self._dragged_event
        self._dragged_event = None
        if callable(self._on_event_moved):
            self._on_event_moved(moving, target_date, target_time)

    @staticmethod
    def _timeline_badge(event):
        """Internal helper for timeline badge."""
        event_date = event.get("date")
        if event_date is None:
            return "upcoming"

        from datetime import date as _date

        today = _date.today()
        if event_date < today:
            return "overdue"
        if event_date == today:
            return "today"
        return "upcoming"

    def _emit_day_selected(self, selected_date):
        """Internal helper for emit day selected."""
        if callable(self._on_day_selected):
            self._on_day_selected(selected_date)

    def _emit_cell_click(self, selected_date, start_time=None):
        """Internal helper for emit cell click."""
        self._emit_day_selected(selected_date)
        if callable(self._on_cell_click):
            self._on_cell_click(selected_date, start_time)

    def _emit_cell_double_click(self, selected_date, start_time=None):
        """Internal helper for emit cell double click."""
        if callable(self._on_cell_double_click):
            self._on_cell_double_click(selected_date, start_time)

    def _emit_event_click(self, event):
        """Internal helper for emit event click."""
        if callable(self._on_event_click):
            self._on_event_click(event)

    @staticmethod
    def _day_color(events):
        """Internal helper for day color."""
        if not events:
            return "transparent"
        first = events[0] or {}
        return first.get("color") or "transparent"
