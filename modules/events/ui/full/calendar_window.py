from datetime import date, timedelta
import tkinter as tk

import customtkinter as ctk

from .calendar_grid_panel import CalendarGridPanel
from .event_detail_panel import EventDetailPanel
from .navigation_panel import NavigationPanel
from .event_editor_dialog import EventEditorDialog
from .quick_add_popover import QuickAddPopover
from modules.events.services.entity_link_service import EntityLinkService


class CalendarWindow(ctk.CTkToplevel):
    """Dedicated full calendar window with split panels and callback-based interactions."""

    VIEW_MONTH = "month"
    VIEW_WEEK = "week"
    VIEW_DAY = "day"
    VIEW_TIMELINE = "timeline"
    VIEW_AGENDA = "agenda"
    SUPPORTED_VIEWS = {VIEW_MONTH, VIEW_WEEK, VIEW_DAY, VIEW_TIMELINE, VIEW_AGENDA}

    def __init__(
        self,
        master,
        get_events_for_day,
        get_events_for_range,
        on_create_event=None,
        on_update_event=None,
        initial_date=None,
        initial_view_mode="month",
        on_state_change=None,
        on_open_entity=None,
        entity_link_service=None,
    ):
        super().__init__(master)
        self.title("Calendrier complet")
        self.geometry("1250x760")
        self.transient(master)

        self.get_events_for_day = get_events_for_day
        self.get_events_for_range = get_events_for_range
        self.on_create_event = on_create_event
        self.on_update_event = on_update_event
        self.on_state_change = on_state_change
        self.on_open_entity = on_open_entity

        self.entity_link_service = entity_link_service or EntityLinkService(getattr(master, "entity_wrappers", {}))

        self.active_date = initial_date or date.today()
        self.view_mode = self._normalize_view_mode(initial_view_mode)
        self.anchor_date = self.active_date
        self.panel_filters = {
            "show_source": True,
            "search_text": "",
            "type": "",
            "entity": "",
            "status": "",
            "agenda_window_days": 7,
        }
        self.is_detail_compact = False

        self._build_ui()
        self._bind_responsive_events()

        self.protocol("WM_DELETE_WINDOW", self._close_window)
        self.after_idle(self._raise_above_parent)
        self._render()

    def _raise_above_parent(self):
        """Ensure the calendar opens above the main window without staying always-on-top."""
        try:
            self.attributes("-topmost", True)
            self.lift()
            self.focus_force()
            self.after(150, lambda: self.attributes("-topmost", False))
        except Exception:
            return

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
            on_new_event=self._open_full_editor,
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
            get_events_for_range=self.get_events_for_range,
            on_day_selected=self._select_day,
            on_cell_double_click=self._on_calendar_cell_double_click,
            on_event_moved=self._on_event_moved,
        )

        self.event_detail_panel = EventDetailPanel(
            center_pane,
            on_compact_toggle=self._on_compact_toggle,
            on_quick_edit=self._on_quick_edit,
            on_open_entity=self._on_open_entity,
        )

        outer_pane.add(self.navigation_panel, minsize=220, stretch="never")
        outer_pane.add(center_pane, minsize=700, stretch="always")
        center_pane.add(self.calendar_grid_panel, minsize=420, stretch="always")
        center_pane.add(self.event_detail_panel, minsize=250, stretch="always")

    def _bind_responsive_events(self):
        self.bind("<Configure>", self._on_window_resized)
        self.bind("<KeyPress-n>", self._on_new_event_shortcut)
        self.bind("<KeyPress-N>", self._on_new_event_shortcut)

    def _on_window_resized(self, event):
        if event.widget is not self:
            return
        should_compact = event.width < 980
        if should_compact != self.is_detail_compact:
            self.is_detail_compact = should_compact
            self.event_detail_panel.set_compact_mode(self.is_detail_compact)

    def _on_filters_changed(self, filters):
        self.panel_filters.update(filters)
        self._render()

    def _on_compact_toggle(self, is_compact):
        self.is_detail_compact = bool(is_compact)

    def _on_quick_edit(self, event, new_title):
        event["title"] = new_title
        self._render_detail_panel()

    def _on_event_moved(self, event, target_date, target_time=None):
        if not callable(self.on_update_event):
            return
        if self.on_update_event(event, target_date=target_date, target_time=target_time):
            self.active_date = target_date
            self.anchor_date = target_date
            self._render()
            self._emit_state_change()


    def _on_open_entity(self, entity_type, entity_name):
        if callable(self.on_open_entity):
            self.on_open_entity(entity_type, entity_name)

    def _on_new_event_shortcut(self, _event=None):
        self._open_full_editor()

    def _open_full_editor(self):
        initial_values = {
            "date": self.active_date,
        }

        def _save_from_editor(payload):
            self._create_event(payload)

        EventEditorDialog(
            self,
            initial_values=initial_values,
            on_save=_save_from_editor,
            entity_link_service=self.entity_link_service,
        )

    def _on_calendar_cell_double_click(self, selected_date, start_time=None):
        self._select_day(selected_date)
        self._open_quick_add(selected_date, start_time=start_time)

    def _open_quick_add(self, selected_date, start_time=None):
        QuickAddPopover(
            self,
            initial_date=selected_date,
            initial_start_time=start_time,
            on_create=self._create_event,
            on_more_options=self._create_event,
        )

    def _create_event(self, payload):
        if not callable(self.on_create_event):
            return
        created = self.on_create_event(payload)
        if not created:
            return
        created_date = created.get("date")
        if created_date is not None:
            self.active_date = created_date
            self.anchor_date = created_date
        self._render()
        self._emit_state_change()

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
        filtered_events = self._filtered_events()
        unique_types = sorted({str(event.get("type") or "").strip() for event in filtered_events if event.get("type")})
        unique_statuses = sorted({str(event.get("status") or "").strip() for event in filtered_events if event.get("status")})
        linked_entities = sorted(
            {
                linked
                for event in filtered_events
                for key in ("Places", "NPCs", "Scenarios", "Informations")
                for linked in (event.get(key) or [])
                if linked
            }
        )

        self.navigation_panel.set_filter_options(types=unique_types, entities=linked_entities, statuses=unique_statuses)
        self.navigation_panel.set_state(
            active_date=self.active_date,
            anchor_date=self.anchor_date,
            view_mode=self.view_mode,
        )
        self.calendar_grid_panel.render(
            view_mode=self.view_mode,
            anchor_date=self.anchor_date,
            active_date=self.active_date,
            filters=self.panel_filters,
            filter_predicate=self._passes_filters,
        )
        self._render_detail_panel()

    def _render_detail_panel(self):
        events = [event for event in self.get_events_for_day(self.active_date) if self._passes_filters(event)]
        self.event_detail_panel.render(
            active_date=self.active_date,
            events=events,
            show_source=bool(self.panel_filters.get("show_source", True)),
        )
        self.event_detail_panel.set_compact_mode(self.is_detail_compact)

    def _filtered_events(self):
        return [event for event in self.get_events_for_range(date.min, date.max) if self._passes_filters(event)]

    def _passes_filters(self, event):
        text = str(self.panel_filters.get("search_text") or "").strip().lower()
        type_filter = str(self.panel_filters.get("type") or "").strip().lower()
        entity_filter = str(self.panel_filters.get("entity") or "").strip().lower()
        status_filter = str(self.panel_filters.get("status") or "").strip().lower()

        if type_filter and type_filter != str(event.get("type") or "").strip().lower():
            return False
        if status_filter and status_filter != str(event.get("status") or "").strip().lower():
            return False

        linked = [
            str(name).strip().lower()
            for key in ("Places", "NPCs", "Scenarios", "Informations")
            for name in (event.get(key) or [])
        ]
        if entity_filter and entity_filter not in linked:
            return False

        if text:
            haystack = [
                str(event.get("title") or "").lower(),
                str(event.get("type") or "").lower(),
                str(event.get("status") or "").lower(),
                " ".join(linked),
            ]
            if text not in " ".join(haystack):
                return False

        return True

    def _close_window(self):
        self.withdraw()

    def _emit_state_change(self):
        if callable(self.on_state_change):
            self.on_state_change(self.active_date, self.view_mode)
