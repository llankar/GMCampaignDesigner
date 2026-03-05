import calendar
from datetime import date

import customtkinter as ctk


class NavigationPanel(ctk.CTkFrame):
    """Navigation sidebar: quick date picker, view mode and simple filters."""

    VIEW_LABELS = {
        "month": "Mois",
        "week": "Semaine",
        "day": "Jour",
        "timeline": "Timeline",
    }

    def __init__(
        self,
        master,
        *,
        on_previous,
        on_next,
        on_today,
        on_view_change,
        on_date_selected,
        on_filter_changed,
    ):
        super().__init__(master)
        self._on_previous = on_previous
        self._on_next = on_next
        self._on_today = on_today
        self._on_view_change = on_view_change
        self._on_date_selected = on_date_selected
        self._on_filter_changed = on_filter_changed

        self._month_cells = []
        self._month_matrix = []
        self._active_date = date.today()
        self._anchor_date = self._active_date

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(5, weight=1)

        self._build_controls()

    def _build_controls(self):
        nav = ctk.CTkFrame(self, fg_color="transparent")
        nav.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 8))
        ctk.CTkButton(nav, text="◀", width=34, command=self._on_previous).pack(side="left", padx=(0, 6))
        ctk.CTkButton(nav, text="Aujourd'hui", width=90, command=self._on_today).pack(side="left", padx=(0, 6))
        ctk.CTkButton(nav, text="▶", width=34, command=self._on_next).pack(side="left")

        self.period_label = ctk.CTkLabel(self, text="", font=ctk.CTkFont(size=14, weight="bold"), anchor="w")
        self.period_label.grid(row=1, column=0, sticky="ew", padx=10)

        self.view_mode_switch = ctk.CTkSegmentedButton(
            self,
            values=list(self.VIEW_LABELS.values()),
            command=self._handle_view_change,
        )
        self.view_mode_switch.grid(row=2, column=0, sticky="ew", padx=10, pady=(8, 10))

        cal_frame = ctk.CTkFrame(self)
        cal_frame.grid(row=3, column=0, sticky="ew", padx=10, pady=(0, 8))
        for idx, label in enumerate(("L", "M", "M", "J", "V", "S", "D")):
            ctk.CTkLabel(cal_frame, text=label).grid(row=0, column=idx, padx=2, pady=(4, 2), sticky="ew")

        self._month_cells = []
        for week_idx in range(6):
            row = []
            for day_idx in range(7):
                btn = ctk.CTkButton(
                    cal_frame,
                    text="",
                    width=28,
                    height=26,
                    fg_color="transparent",
                    command=lambda w=week_idx, d=day_idx: self._select_cell(w, d),
                )
                btn.grid(row=week_idx + 1, column=day_idx, padx=2, pady=2)
                row.append(btn)
            self._month_cells.append(row)

        filters = ctk.CTkFrame(self)
        filters.grid(row=4, column=0, sticky="ew", padx=10, pady=(0, 10))
        ctk.CTkLabel(filters, text="Filtres", anchor="w").pack(fill="x", padx=8, pady=(8, 4))
        self._source_filter = ctk.CTkCheckBox(filters, text="Afficher la source", command=self._emit_filter_change)
        self._source_filter.select()
        self._source_filter.pack(anchor="w", padx=8, pady=(0, 8))

    def set_state(self, *, active_date, anchor_date, view_mode):
        self._active_date = active_date
        self._anchor_date = anchor_date
        self.period_label.configure(text=anchor_date.strftime("%B %Y").capitalize())

        mode_label = self.VIEW_LABELS.get(view_mode, self.VIEW_LABELS["month"])
        self.view_mode_switch.set(mode_label)
        self._render_month_grid()

    def _render_month_grid(self):
        matrix = calendar.Calendar(firstweekday=0).monthdatescalendar(self._anchor_date.year, self._anchor_date.month)
        self._month_matrix = matrix

        for week_idx, week in enumerate(self._month_cells):
            week_dates = matrix[week_idx] if week_idx < len(matrix) else [None] * 7
            for day_idx, btn in enumerate(week):
                day_date = week_dates[day_idx]
                if day_date is None:
                    btn.configure(text="", state="disabled")
                    continue
                is_selected = day_date == self._active_date
                is_current_month = day_date.month == self._anchor_date.month
                btn.configure(
                    text=str(day_date.day),
                    state="normal",
                    fg_color=("#2f6cc0", "#2f6cc0") if is_selected else "transparent",
                    text_color=("#1a1a1a", "#f0f0f0") if is_current_month else ("#999999", "#666666"),
                )

    def _handle_view_change(self, selected_label):
        reverse = {value: key for key, value in self.VIEW_LABELS.items()}
        selected_mode = reverse.get(selected_label, "month")
        if callable(self._on_view_change):
            self._on_view_change(selected_mode)

    def _select_cell(self, week_index, day_index):
        if week_index >= len(self._month_matrix):
            return
        selected_date = self._month_matrix[week_index][day_index]
        if callable(self._on_date_selected):
            self._on_date_selected(selected_date)

    def _emit_filter_change(self):
        if callable(self._on_filter_changed):
            self._on_filter_changed({"show_source": bool(self._source_filter.get())})
