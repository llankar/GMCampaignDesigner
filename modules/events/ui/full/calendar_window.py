from datetime import date, timedelta
import tkinter as tk

import customtkinter as ctk

from .calendar_grid_panel import CalendarGridPanel
from .event_detail_panel import EventDetailPanel
from .navigation_panel import NavigationPanel


class CalendarWindow(ctk.CTkToplevel):
    """Dedicated full calendar window with split panels and callback-based interactions."""

    VIEW_MONTH = "month"
    VIEW_WEEK = "week"
    VIEW_DAY = "day"
    VIEW_TIMELINE = "timeline"
    SUPPORTED_VIEWS = {VIEW_MONTH, VIEW_WEEK, VIEW_DAY, VIEW_TIMELINE}

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
        self.geometry("1250x760")

        self.get_events_for_day = get_events_for_day
        self.get_events_for_range = get_events_for_range
        self.on_state_change = on_state_change

        self.active_date = initial_date or date.today()
        self.view_mode = self._normalize_view_mode(initial_view_mode)
        self.anchor_date = self.active_date
        self.panel_filters = {"show_source": True}
        self.is_detail_compact = False

        self._build_ui()
        self._bind_responsive_events()

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
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        outer_pane = tk.PanedWindow(self, orient=tk.HORIZONTAL, sashrelief=tk.RAISED, sashwidth=6, bd=0)
        outer_pane.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

        self.navigation_panel = NavigationPanel(
            outer_pane,
            on_previous=self._go_previous,
            on_next=self._go_next,
            on_today=self._jump_today,
            on_view_change=self.set_view_mode,
            on_date_selected=self._select_day,
            on_filter_changed=self._on_filters_changed,
        )

        center_pane = tk.PanedWindow(outer_pane, orient=tk.HORIZONTAL, sashrelief=tk.RAISED, sashwidth=6, bd=0)

        self.calendar_grid_panel = CalendarGridPanel(
            center_pane,
            get_events_for_day=self.get_events_for_day,
            on_day_selected=self._select_day,
        )

        self.event_detail_panel = EventDetailPanel(
            center_pane,
            on_compact_toggle=self._on_compact_toggle,
            on_quick_edit=self._on_quick_edit,
        )

        outer_pane.add(self.navigation_panel, minsize=220, stretch="never")
        outer_pane.add(center_pane, minsize=700, stretch="always")
        center_pane.add(self.calendar_grid_panel, minsize=420, stretch="always")
        center_pane.add(self.event_detail_panel, minsize=250, stretch="always")

    def _bind_responsive_events(self):
        self.bind("<Configure>", self._on_window_resized)

    def _on_window_resized(self, event):
        if event.widget is not self:
            return
        should_compact = event.width < 980
        if should_compact != self.is_detail_compact:
            self.is_detail_compact = should_compact
            self.event_detail_panel.set_compact_mode(self.is_detail_compact)

    def _on_filters_changed(self, filters):
        self.panel_filters.update(filters)
        self._render_detail_panel()

    def _on_compact_toggle(self, is_compact):
        self.is_detail_compact = bool(is_compact)

    def _on_quick_edit(self, event, new_title):
        event["title"] = new_title
        self._render_detail_panel()

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

    def _select_day(self, selected_date):
        self.active_date = selected_date
        self.anchor_date = selected_date
        self._render()
        self._emit_state_change()

    def _render(self):
        self.navigation_panel.set_state(
            active_date=self.active_date,
            anchor_date=self.anchor_date,
            view_mode=self.view_mode,
        )
        self.calendar_grid_panel.render(
            view_mode=self.view_mode,
            anchor_date=self.anchor_date,
            active_date=self.active_date,
        )
        self._render_detail_panel()

    def _render_detail_panel(self):
        events = self.get_events_for_day(self.active_date)
        self.event_detail_panel.render(
            active_date=self.active_date,
            events=events,
            show_source=bool(self.panel_filters.get("show_source", True)),
        )
        self.event_detail_panel.set_compact_mode(self.is_detail_compact)

    def _close_window(self):
        self.withdraw()

    def _emit_state_change(self):
        if callable(self.on_state_change):
            self.on_state_change(self.active_date, self.view_mode)
