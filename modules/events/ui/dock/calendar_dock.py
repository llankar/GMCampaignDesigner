import calendar
import customtkinter as ctk

from modules.events.services.campaign_date_service import CampaignDateService
from modules.events.ui.dock.date_agenda_dialog import CampaignDateAgendaDialog


class CalendarDock(ctk.CTkFrame):
    def __init__(self, master, on_date_selected=None, on_set_campaign_today=None):
        super().__init__(master, width=320, corner_radius=8)
        self.grid_propagate(False)
        self.on_date_selected = on_date_selected
        self.on_set_campaign_today = on_set_campaign_today

        campaign_today = CampaignDateService.get_today()
        self.display_year = campaign_today.year
        self.display_month = campaign_today.month
        self.selected_date = campaign_today

        self._day_buttons = []
        self._events_by_date = {}
        self._selected_event_line_widgets = []
        self._upcoming_event_line_widgets = []

        self._build_ui()
        self._render_month()

    def _build_ui(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=8, pady=(8, 4))

        ctk.CTkButton(header, text="◀", width=28, command=self._previous_month).pack(side="left")
        self.month_label = ctk.CTkLabel(header, text="", font=ctk.CTkFont(size=14, weight="bold"))
        self.month_label.pack(side="left", expand=True)
        ctk.CTkButton(header, text="▶", width=28, command=self._next_month).pack(side="right")

        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.pack(fill="x", padx=8, pady=(0, 2))
        self.campaign_today_label = ctk.CTkLabel(bar, text="", anchor="w")
        self.campaign_today_label.pack(side="left", fill="x", expand=True)
        self.campaign_today_label.bind("<Button-1>", self._open_campaign_today_dialog)
        ctk.CTkButton(bar, text="Définir jour", width=100, command=self._open_campaign_today_dialog).pack(side="right")

        calendar_frame = ctk.CTkFrame(self)
        calendar_frame.pack(fill="x", padx=8, pady=4)

        for column, label in enumerate(("L", "M", "M", "J", "V", "S", "D")):
            ctk.CTkLabel(calendar_frame, text=label, width=34).grid(row=0, column=column, padx=1, pady=(4, 2))

        for week in range(6):
            row_buttons = []
            for day in range(7):
                button = ctk.CTkButton(
                    calendar_frame,
                    text="",
                    width=34,
                    height=28,
                    fg_color="transparent",
                    hover_color=("#d9d9d9", "#3a3a3a"),
                    command=lambda w=week, d=day: self._select_from_cell(w, d),
                )
                button.grid(row=week + 1, column=day, padx=1, pady=1)
                row_buttons.append(button)
            self._day_buttons.append(row_buttons)

        events_frame = ctk.CTkFrame(self)
        events_frame.pack(fill="both", expand=True, padx=8, pady=(4, 8))

        self.selected_title_label = ctk.CTkLabel(events_frame, text="Aujourd'hui", anchor="w", font=ctk.CTkFont(size=13, weight="bold"))
        self.selected_title_label.pack(fill="x", padx=8, pady=(8, 4))

        self.selected_events_box = ctk.CTkScrollableFrame(events_frame, height=100)
        self.selected_events_box.pack(fill="x", padx=8, pady=(0, 8))

        upcoming_label = ctk.CTkLabel(events_frame, text="Prochains évènements", anchor="w", font=ctk.CTkFont(size=13, weight="bold"))
        upcoming_label.pack(fill="x", padx=8, pady=(4, 4))

        self.upcoming_events_box = ctk.CTkScrollableFrame(events_frame, height=140)
        self.upcoming_events_box.pack(fill="both", expand=True, padx=8, pady=(0, 8))

    def _render_month(self):
        campaign_today = CampaignDateService.get_today()
        self.campaign_today_label.configure(text=f"Jour campagne : {campaign_today.strftime('%d/%m/%Y')}")
        self.month_label.configure(text=f"{calendar.month_name[self.display_month]} {self.display_year}")

        month_matrix = calendar.Calendar(firstweekday=0).monthdatescalendar(self.display_year, self.display_month)
        self._cell_dates = month_matrix

        for week_index, week_dates in enumerate(month_matrix):
            for day_index, day_date in enumerate(week_dates):
                button = self._day_buttons[week_index][day_index]
                is_current_month = day_date.month == self.display_month
                is_selected = day_date == self.selected_date
                day_events = self._events_by_date.get(day_date, [])
                marker = "•" if day_events else ""
                first_color = (day_events[0].get("color") if day_events else None) or "transparent"
                button.configure(
                    text=f"{day_date.day}{marker}",
                    state="normal",
                    text_color=("#1a1a1a", "#f0f0f0") if is_current_month else ("#999999", "#666666"),
                    fg_color=("#2f6cc0", "#2f6cc0") if is_selected else first_color,
                )

    def _select_from_cell(self, week_index, day_index):
        selected = self._cell_dates[week_index][day_index]
        self.selected_date = selected
        self.display_year = selected.year
        self.display_month = selected.month
        self._render_month()
        if callable(self.on_date_selected):
            self.on_date_selected(selected)

    def _previous_month(self):
        if self.display_month == 1:
            self.display_month = 12
            self.display_year -= 1
        else:
            self.display_month -= 1
        self._render_month()

    def _next_month(self):
        if self.display_month == 12:
            self.display_month = 1
            self.display_year += 1
        else:
            self.display_month += 1
        self._render_month()

    def set_selected_date_events(self, selected_date, events):
        self.selected_date = selected_date
        self.selected_title_label.configure(text=f"Évènements du {selected_date.strftime('%d/%m/%Y')}")
        self._populate_event_list(
            self.selected_events_box,
            self._selected_event_line_widgets,
            events,
            include_date=False,
            empty_message="Aucun évènement.",
        )
        self._render_month()

    def set_upcoming_events(self, events):
        self._populate_event_list(
            self.upcoming_events_box,
            self._upcoming_event_line_widgets,
            events,
            include_date=True,
            empty_message="Aucun évènement à venir.",
        )

    def set_month_event_map(self, events_by_date):
        if isinstance(events_by_date, dict):
            self._events_by_date = dict(events_by_date)
        else:
            self._events_by_date = {}
        self._render_month()

    @staticmethod
    def _event_badge(event):
        event_date = event.get("date")
        if event_date is None:
            return "à venir"
        today = CampaignDateService.get_today()
        if event_date < today:
            return "en retard"
        if event_date == today:
            return "aujourd'hui"
        return "à venir"

    def _open_campaign_today_dialog(self, _event=None):
        CampaignDateAgendaDialog(self, on_apply=self._on_campaign_today_applied)

    def _set_campaign_today_from_selection(self):
        campaign_today = CampaignDateService.set_today(self.selected_date)
        self._on_campaign_today_applied(campaign_today)

    def _on_campaign_today_applied(self, campaign_today):
        self.selected_date = campaign_today
        self.display_year = campaign_today.year
        self.display_month = campaign_today.month
        if callable(self.on_set_campaign_today):
            self.on_set_campaign_today(campaign_today)
        self._render_month()

    @classmethod
    def _format_event_line(cls, event, include_date=False):
        title = event.get("title", "Sans titre")
        badge = cls._event_badge(event)
        if include_date:
            event_date = event.get("date")
            if event_date:
                return f"• {event_date.strftime('%d/%m')} — {title} [{badge}]"
        return f"• {title} [{badge}]"

    @classmethod
    def _populate_event_list(cls, container, cache, events, *, include_date=False, empty_message="Aucun évènement"):
        for widget in cache:
            try:
                widget.destroy()
            except Exception:
                pass
        cache.clear()

        if not events:
            empty_label = ctk.CTkLabel(container, text=empty_message, anchor="w", justify="left", text_color="gray")
            empty_label.pack(fill="x", padx=2, pady=2)
            cache.append(empty_label)
            return

        for event in events:
            label = ctk.CTkLabel(
                container,
                text=cls._format_event_line(event, include_date=include_date),
                anchor="w",
                justify="left",
                text_color=event.get("color") or ("#1a1a1a", "#f0f0f0"),
            )
            label.pack(fill="x", padx=2, pady=2)
            cache.append(label)
