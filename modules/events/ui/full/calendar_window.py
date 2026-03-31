"""Window for event calendar."""

from datetime import date, timedelta
import tkinter as tk

import customtkinter as ctk

from .calendar_grid_panel import CalendarGridPanel
from .event_detail_panel import EventDetailPanel
from .navigation_panel import NavigationPanel
from .event_editor_dialog import EventEditorDialog
from .quick_add_popover import QuickAddPopover
from modules.events.services.entity_link_service import EntityLinkService
from modules.events.services.campaign_date_service import CampaignDateService


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
        on_open_timeline_simulator=None,
        initial_date=None,
        initial_view_mode="month",
        on_state_change=None,
        initial_filters=None,
        initial_panel_widths=None,
        on_open_entity=None,
        entity_link_service=None,
    ):
        """Initialize the CalendarWindow instance."""
        super().__init__(master)
        self.title("Calendrier complet")
        self.geometry("1250x760")
        self.transient(master)

        self.get_events_for_day = get_events_for_day
        self.get_events_for_range = get_events_for_range
        self.on_create_event = on_create_event
        self.on_update_event = on_update_event
        self.on_open_timeline_simulator = on_open_timeline_simulator
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
        if isinstance(initial_filters, dict):
            self.panel_filters.update(initial_filters)
        self.is_detail_compact = False

        self._build_ui(initial_panel_widths=initial_panel_widths)
        self._bind_responsive_events()

        self.protocol("WM_DELETE_WINDOW", self._close_window)
        self.after_idle(self._raise_above_parent)
        self._render()

    def _raise_above_parent(self):
        """Ensure the calendar opens above the main window without staying always-on-top."""
        try:
            # Keep raise above parent resilient if this step fails.
            self.attributes("-topmost", True)
            self.lift()
            self.focus_force()
            self.after(150, lambda: self.attributes("-topmost", False))
        except Exception:
            return

    @classmethod
    def _normalize_view_mode(cls, mode):
        """Normalize view mode."""
        normalized = str(mode or "").lower().strip()
        if normalized in cls.SUPPORTED_VIEWS:
            return normalized
        return cls.VIEW_MONTH

    @staticmethod
    def _start_of_week(target_date):
        """Start of week."""
        return target_date - timedelta(days=target_date.weekday())

    def _build_ui(self, initial_panel_widths=None):
        """Build UI."""
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        outer_pane = tk.PanedWindow(self, orient=tk.HORIZONTAL, sashrelief=tk.RAISED, sashwidth=6, bd=0)
        self.outer_pane = outer_pane
        outer_pane.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

        self.navigation_panel = NavigationPanel(
            outer_pane,
            on_new_event=self._open_full_editor,
            on_open_timeline_simulator=self._open_timeline_simulator,
            on_previous=self._go_previous,
            on_next=self._go_next,
            on_today=self._jump_today,
            on_view_change=self.set_view_mode,
            on_date_selected=self._select_day,
            on_filter_changed=self._on_filters_changed,
        )

        center_pane = tk.PanedWindow(outer_pane, orient=tk.HORIZONTAL, sashrelief=tk.RAISED, sashwidth=6, bd=0)
        self.center_pane = center_pane

        self.calendar_grid_panel = CalendarGridPanel(
            center_pane,
            get_events_for_day=self.get_events_for_day,
            get_events_for_range=self.get_events_for_range,
            on_day_selected=self._select_day,
            on_cell_click=self._on_calendar_cell_click,
            on_cell_double_click=self._on_calendar_cell_double_click,
            on_event_moved=self._on_event_moved,
            on_event_click=self._on_calendar_event_click,
        )

        self.event_detail_panel = EventDetailPanel(
            center_pane,
            on_compact_toggle=self._on_compact_toggle,
            on_quick_edit=self._on_quick_edit,
            on_open_entity=self._on_open_entity,
            on_event_click=self._on_calendar_event_click,
        )

        outer_pane.add(self.navigation_panel, minsize=220, stretch="never")
        outer_pane.add(center_pane, minsize=700, stretch="always")
        center_pane.add(self.calendar_grid_panel, minsize=420, stretch="always")
        center_pane.add(self.event_detail_panel, minsize=250, stretch="always")

        self.navigation_panel.set_filters(self.panel_filters)
        self.after_idle(lambda: self._restore_panel_widths(initial_panel_widths or {}))


    def _bind_responsive_events(self):
        """Bind responsive events."""
        self.bind("<Configure>", self._on_window_resized)
        self.bind("<KeyPress-n>", self._on_new_event_shortcut)
        self.bind("<KeyPress-N>", self._on_new_event_shortcut)
        self.bind("<ButtonRelease-1>", self._on_sash_interaction, add="+")

    def _on_window_resized(self, event):
        """Handle window resized."""
        if event.widget is not self:
            return
        should_compact = event.width < 980
        if should_compact != self.is_detail_compact:
            self.is_detail_compact = should_compact
            self.event_detail_panel.set_compact_mode(self.is_detail_compact)

    def _on_filters_changed(self, filters):
        """Handle filters changed."""
        self.panel_filters.update(filters)
        self._render()
        self._emit_state_change()

    def _on_compact_toggle(self, is_compact):
        """Handle compact toggle."""
        self.is_detail_compact = bool(is_compact)
        self._emit_state_change()

    def _on_quick_edit(self, event, new_title):
        """Handle quick edit."""
        event["title"] = new_title
        self._render_detail_panel()

    def _on_event_moved(self, event, target_date, target_time=None):
        """Handle event moved."""
        if not callable(self.on_update_event):
            return
        if self.on_update_event(event, target_date=target_date, target_time=target_time):
            self.active_date = target_date
            self.anchor_date = target_date
            self._render()
            self._emit_state_change()

    def _on_calendar_event_click(self, event):
        """Handle calendar event click."""
        if not isinstance(event, dict):
            return
        self._open_event_editor(event)


    def _on_open_entity(self, entity_type, entity_name):
        """Handle open entity."""
        if callable(self.on_open_entity):
            self.on_open_entity(entity_type, entity_name)

    def _open_timeline_simulator(self):
        """Open timeline simulator."""
        if callable(self.on_open_timeline_simulator):
            self.on_open_timeline_simulator(parent=self, target_date=self.active_date)

    def _on_new_event_shortcut(self, _event=None):
        """Handle new event shortcut."""
        self._open_full_editor()

    def _open_full_editor(self):
        """Open full editor."""
        initial_values = {
            "date": self.active_date,
        }

        def _save_from_editor(payload):
            """Save from editor."""
            self._create_event(payload)

        EventEditorDialog(
            self,
            initial_values=initial_values,
            on_save=_save_from_editor,
            entity_link_service=self.entity_link_service,
        )

    def _open_event_editor(self, event):
        """Open event editor."""
        initial_values = {
            "title": event.get("title") or "",
            "date": event.get("date"),
            "start_time": event.get("time") or "",
            "end_time": event.get("end_time") or "",
            "type": event.get("type") or "Session",
            "color": event.get("color") or "",
            "status": event.get("status") or "",
            "Places": event.get("Places") or [],
            "NPCs": event.get("NPCs") or [],
            "Villains": event.get("Villains") or [],
            "Scenarios": event.get("Scenarios") or [],
            "Creatures": event.get("Creatures") or [],
            "Objects": event.get("Objects") or [],
            "Factions": event.get("Factions") or [],
            "Bases": event.get("Bases") or [],
            "Maps": event.get("Maps") or [],
            "Clues": event.get("Clues") or [],
            "Informations": event.get("Informations") or [],
        }

        def _save_from_editor(payload):
            """Save from editor."""
            self._update_event(event, payload)

        EventEditorDialog(
            self,
            initial_values=initial_values,
            on_save=_save_from_editor,
            entity_link_service=self.entity_link_service,
            save_label="Enregistrer",
        )

    def _update_event(self, event, payload):
        """Update event."""
        if not callable(self.on_update_event):
            return

        new_date = payload.get("date")
        if self.on_update_event(event, target_date=new_date, payload=payload):
            # Handle the branch where on_update_event(event, target_date=new_date, payload=payload).
            resolved_date = payload.get("date")
            if isinstance(resolved_date, date):
                self.active_date = resolved_date
                self.anchor_date = resolved_date
            self._render()
            self._emit_state_change()

    def _on_calendar_cell_click(self, selected_date, start_time=None):
        """Handle calendar cell click."""
        self._select_day(selected_date)
        self._open_quick_add(selected_date, start_time=start_time)

    def _on_calendar_cell_double_click(self, selected_date, start_time=None):
        """Handle calendar cell double click."""
        self._select_day(selected_date)

    def _open_quick_add(self, selected_date, start_time=None):
        """Open quick add."""
        QuickAddPopover(
            self,
            initial_date=selected_date,
            initial_start_time=start_time,
            on_create=self._create_event,
            on_more_options=self._create_event,
        )

    def _create_event(self, payload):
        """Create event."""
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
        """Internal helper for go previous."""
        if self.view_mode == self.VIEW_MONTH:
            # Handle the branch where view_mode == VIEW_MONTH.
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
        """Internal helper for go next."""
        if self.view_mode == self.VIEW_MONTH:
            # Handle the branch where view_mode == VIEW_MONTH.
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
        """Internal helper for jump today."""
        self.focus_date(CampaignDateService.get_today(), view_mode=self.view_mode, auto_select=True)

    def set_view_mode(self, view_mode):
        """Set view mode."""
        normalized = self._normalize_view_mode(view_mode)
        if normalized == self.view_mode:
            return
        self.view_mode = normalized
        self.anchor_date = self.active_date
        self._render()
        self._emit_state_change()

    def focus_date(self, target_date, view_mode=None, auto_select=True):
        """Handle focus date."""
        if target_date is None:
            target_date = CampaignDateService.get_today()
        if view_mode is not None:
            self.view_mode = self._normalize_view_mode(view_mode)

        self.anchor_date = target_date
        if auto_select:
            self.active_date = target_date

        self._render()
        self._emit_state_change()

    def _select_day(self, selected_date):
        """Select day."""
        self.active_date = selected_date
        self.anchor_date = selected_date
        self._render()
        self._emit_state_change()

    def _render(self):
        """Render the operation."""
        filtered_events = self._filtered_events()
        unique_types = sorted({str(event.get("type") or "").strip() for event in filtered_events if event.get("type")})
        unique_statuses = sorted({str(event.get("status") or "").strip() for event in filtered_events if event.get("status")})
        linked_entities = sorted(
            {
                linked
                for event in filtered_events
                for key in ("Places", "NPCs", "Villains", "Creatures", "Objects", "Factions", "Bases", "Maps", "Clues", "Scenarios", "Informations")
                for linked in (event.get(key) or [])
                if linked
            }
        )

        self.navigation_panel.set_filter_options(types=unique_types, entities=linked_entities, statuses=unique_statuses)
        self.navigation_panel.set_filters(self.panel_filters)
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
        """Render detail panel."""
        events = [event for event in self.get_events_for_day(self.active_date) if self._passes_filters(event)]
        self.event_detail_panel.render(
            active_date=self.active_date,
            events=events,
            show_source=bool(self.panel_filters.get("show_source", True)),
        )
        self.event_detail_panel.set_compact_mode(self.is_detail_compact)

    def _filtered_events(self):
        """Internal helper for filtered events."""
        return [event for event in self.get_events_for_range(date.min, date.max) if self._passes_filters(event)]

    def _passes_filters(self, event):
        """Internal helper for passes filters."""
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
            for key in ("Places", "NPCs", "Villains", "Creatures", "Objects", "Factions", "Bases", "Maps", "Clues", "Scenarios", "Informations")
            for name in (event.get(key) or [])
        ]
        if entity_filter and entity_filter not in linked:
            return False

        if text:
            # Continue with this path when text is set.
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
        """Close window."""
        self._emit_state_change()
        self.withdraw()

    def _on_sash_interaction(self, _event=None):
        """Handle sash interaction."""
        self._emit_state_change()

    def _restore_panel_widths(self, panel_widths):
        """Restore panel widths."""
        if not isinstance(panel_widths, dict):
            return
        try:
            left = int(panel_widths.get("left_sidebar")) if panel_widths.get("left_sidebar") is not None else None
        except (TypeError, ValueError):
            left = None
        try:
            center = int(panel_widths.get("center_grid")) if panel_widths.get("center_grid") is not None else None
        except (TypeError, ValueError):
            center = None

        if left is not None and left >= 0:
            try:
                self.outer_pane.sash_place(0, left, 0)
            except Exception:
                pass
        if center is not None and center >= 0:
            try:
                self.center_pane.sash_place(0, center, 0)
            except Exception:
                pass

    def _collect_state(self):
        """Collect state."""
        left_sidebar = None
        center_grid = None
        try:
            left_sidebar = int(self.outer_pane.sash_coord(0)[0])
        except Exception:
            pass
        try:
            center_grid = int(self.center_pane.sash_coord(0)[0])
        except Exception:
            pass

        return {
            "active_date": self.active_date,
            "view_mode": self.view_mode,
            "filters": dict(self.panel_filters),
            "panel_widths": {
                "left_sidebar": left_sidebar,
                "center_grid": center_grid,
            },
        }

    def _emit_state_change(self):
        """Internal helper for emit state change."""
        if callable(self.on_state_change):
            state = self._collect_state()
            self.on_state_change(state)
