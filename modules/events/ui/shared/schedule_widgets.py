import calendar
from datetime import date, datetime
import tkinter as tk

import customtkinter as ctk


def parse_event_date(value):
    if isinstance(value, date):
        return value

    text = str(value or "").strip()
    if not text:
        return None

    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def format_event_date(value):
    parsed = parse_event_date(value)
    if parsed is not None:
        return parsed.isoformat()
    return str(value or "").strip()


def normalize_event_time(value):
    text = str(value or "").strip()
    if not text:
        return ""

    hour = None
    minute = None

    if text.isdigit():
        if len(text) <= 2:
            hour = int(text)
            minute = 0
        elif len(text) == 3:
            hour = int(text[0])
            minute = int(text[1:])
        elif len(text) == 4:
            hour = int(text[:2])
            minute = int(text[2:])
    else:
        cleaned = text.replace(".", ":").replace("h", ":").replace("H", ":")
        if ":" in cleaned:
            parts = [part for part in cleaned.split(":") if part != ""]
            if len(parts) == 1 and parts[0].isdigit():
                hour = int(parts[0])
                minute = 0
            elif len(parts) >= 2 and parts[0].isdigit() and parts[1].isdigit():
                hour = int(parts[0])
                minute = int(parts[1])

    if hour is None or minute is None:
        return text
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return text
    return f"{hour:02d}:{minute:02d}"


def _friendly_date_label(value):
    parsed = parse_event_date(value)
    if parsed is None:
        return "No date selected"
    return parsed.strftime("%A, %d %b %Y")


def _position_popup_near_widget(popup, widget, width, height):
    popup.update_idletasks()
    x = widget.winfo_rootx()
    y = widget.winfo_rooty() + widget.winfo_height() + 4
    popup.geometry(f"{width}x{height}+{x}+{y}")


class EventCalendarPopup(ctk.CTkToplevel):
    def __init__(self, master, *, initial_date=None, on_select=None, title="Choose date"):
        super().__init__(master)
        self.title(title)
        self.resizable(False, False)
        self.transient(master.winfo_toplevel())
        self._on_select = on_select
        self._selected_date = parse_event_date(initial_date) or date.today()
        self._visible_month = date(self._selected_date.year, self._selected_date.month, 1)
        self._day_buttons = []

        self._build_ui()
        self._render_month()
        _position_popup_near_widget(self, master, 320, 300)
        self.grab_set()
        self.focus_force()

    def _build_ui(self):
        self.grid_columnconfigure(tuple(range(7)), weight=1)

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, columnspan=7, padx=10, pady=(10, 6), sticky="ew")
        header.grid_columnconfigure(1, weight=1)

        ctk.CTkButton(header, text="<", width=34, command=self._show_previous_month).grid(
            row=0,
            column=0,
            padx=(0, 6),
            sticky="w",
        )
        self.month_label = ctk.CTkLabel(header, text="", anchor="center")
        self.month_label.grid(row=0, column=1, sticky="ew")
        ctk.CTkButton(header, text=">", width=34, command=self._show_next_month).grid(
            row=0,
            column=2,
            padx=(6, 0),
            sticky="e",
        )

        for idx, name in enumerate(("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")):
            ctk.CTkLabel(self, text=name).grid(row=1, column=idx, padx=4, pady=(0, 4))

        for week_index in range(6):
            row_buttons = []
            for day_index in range(7):
                button = ctk.CTkButton(
                    self,
                    text="",
                    width=36,
                    height=32,
                    command=lambda value=None: None,
                )
                button.grid(row=week_index + 2, column=day_index, padx=4, pady=4, sticky="nsew")
                row_buttons.append(button)
            self._day_buttons.append(row_buttons)

        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.grid(row=8, column=0, columnspan=7, padx=10, pady=(8, 10), sticky="ew")
        ctk.CTkButton(footer, text="Today", command=self._select_today).pack(side="left")
        ctk.CTkButton(footer, text="Cancel", fg_color="transparent", command=self.destroy).pack(side="right")

    def _show_previous_month(self):
        year = self._visible_month.year
        month = self._visible_month.month - 1
        if month == 0:
            year -= 1
            month = 12
        self._visible_month = date(year, month, 1)
        self._render_month()

    def _show_next_month(self):
        year = self._visible_month.year
        month = self._visible_month.month + 1
        if month == 13:
            year += 1
            month = 1
        self._visible_month = date(year, month, 1)
        self._render_month()

    def _select_today(self):
        self._select_date(date.today())

    def _select_date(self, selected):
        if callable(self._on_select):
            self._on_select(selected)
        self.destroy()

    def _render_month(self):
        self.month_label.configure(text=self._visible_month.strftime("%B %Y"))
        month_matrix = calendar.Calendar(firstweekday=0).monthdatescalendar(
            self._visible_month.year,
            self._visible_month.month,
        )
        while len(month_matrix) < len(self._day_buttons):
            month_matrix.append([None] * 7)
        today = date.today()

        for week_index, week in enumerate(month_matrix):
            for day_index, day_value in enumerate(week):
                button = self._day_buttons[week_index][day_index]
                if day_value is None:
                    button.configure(
                        text="",
                        state="disabled",
                        fg_color="#242424",
                        hover_color="#242424",
                        border_width=0,
                        border_color="#242424",
                        command=lambda value=None: None,
                    )
                    continue
                in_month = day_value.month == self._visible_month.month
                is_selected = day_value == self._selected_date
                is_today = day_value == today

                fg_color = "#1f6aa5" if is_selected else ("#3A3A3A" if in_month else "#242424")
                hover_color = "#2f7fc0" if is_selected else ("#4A4A4A" if in_month else "#303030")
                border_width = 2 if is_today else 0

                button.configure(
                    text=str(day_value.day),
                    state="normal",
                    fg_color=fg_color,
                    hover_color=hover_color,
                    border_width=border_width,
                    border_color="#f5c542" if is_today else fg_color,
                    text_color="#FFFFFF" if in_month else "#A0A0A0",
                    command=lambda value=day_value: self._select_date(value),
                )


class EventDatePickerField(ctk.CTkFrame):
    def __init__(
        self,
        master,
        *,
        initial_value="",
        picker_button_text="Calendar",
        today_button_text="Today",
        clear_button_text="Clear",
        empty_hint_text="No date selected",
    ):
        super().__init__(master, fg_color="transparent")
        self._empty_hint_text = empty_hint_text
        self._value_var = tk.StringVar()

        self.grid_columnconfigure(0, weight=1)

        self.entry = ctk.CTkEntry(self, textvariable=self._value_var, placeholder_text="YYYY-MM-DD")
        self.entry.grid(row=0, column=0, padx=(0, 8), pady=0, sticky="ew")
        self.entry.bind("<FocusOut>", self._on_focus_out)

        controls = ctk.CTkFrame(self, fg_color="transparent")
        controls.grid(row=0, column=1, sticky="e")
        ctk.CTkButton(controls, text=picker_button_text, width=88, command=self._open_calendar).pack(side="left")
        ctk.CTkButton(controls, text=today_button_text, width=72, command=self._set_today).pack(side="left", padx=6)
        ctk.CTkButton(
            controls,
            text=clear_button_text,
            width=72,
            fg_color="transparent",
            command=self.clear,
        ).pack(side="left")

        self.hint_label = ctk.CTkLabel(self, text="", anchor="w", text_color="#A8A8A8")
        self.hint_label.grid(row=1, column=0, columnspan=2, pady=(6, 0), sticky="w")

        self.set(initial_value)

    def _open_calendar(self):
        EventCalendarPopup(
            self.entry,
            initial_date=self.get(),
            on_select=lambda selected: self.set(selected),
        )

    def _set_today(self):
        self.set(date.today())

    def _on_focus_out(self, _event=None):
        current = self._value_var.get()
        parsed = parse_event_date(current)
        if parsed is not None:
            self._value_var.set(parsed.isoformat())
        self._refresh_hint()

    def _refresh_hint(self):
        value = self._value_var.get().strip()
        self.hint_label.configure(text=_friendly_date_label(value) if value else self._empty_hint_text)

    def clear(self):
        self._value_var.set("")
        self._refresh_hint()

    def set(self, value):
        formatted = format_event_date(value)
        self._value_var.set(formatted)
        self._refresh_hint()

    def get(self):
        return format_event_date(self._value_var.get())


class EventTimePickerPopup(ctk.CTkToplevel):
    def __init__(self, master, *, initial_value="", on_select=None, title="Choose time"):
        super().__init__(master)
        self.title(title)
        self.resizable(False, False)
        self.transient(master.winfo_toplevel())
        self._on_select = on_select

        normalized = normalize_event_time(initial_value)
        hour_value = "--"
        minute_value = "--"
        if normalized and len(normalized) == 5 and normalized[2] == ":":
            hour_value, minute_value = normalized.split(":")

        self.hour_var = tk.StringVar(value=hour_value)
        self.minute_var = tk.StringVar(value=minute_value)

        self._build_ui()
        _position_popup_near_widget(self, master, 240, 140)
        self.grab_set()
        self.focus_force()

    def _build_ui(self):
        container = ctk.CTkFrame(self)
        container.pack(fill="both", expand=True, padx=12, pady=12)
        container.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkLabel(container, text="Hour").grid(row=0, column=0, padx=(0, 6), pady=(0, 6), sticky="w")
        ctk.CTkLabel(container, text="Minute").grid(row=0, column=1, padx=(6, 0), pady=(0, 6), sticky="w")

        hour_values = ["--"] + [f"{hour:02d}" for hour in range(24)]
        minute_values = ["--"] + [f"{minute:02d}" for minute in range(60)]

        self.hour_menu = ctk.CTkOptionMenu(container, values=hour_values, variable=self.hour_var)
        self.hour_menu.grid(row=1, column=0, padx=(0, 6), sticky="ew")
        self.minute_menu = ctk.CTkOptionMenu(container, values=minute_values, variable=self.minute_var)
        self.minute_menu.grid(row=1, column=1, padx=(6, 0), sticky="ew")

        footer = ctk.CTkFrame(container, fg_color="transparent")
        footer.grid(row=2, column=0, columnspan=2, pady=(12, 0), sticky="ew")
        ctk.CTkButton(footer, text="Clear", fg_color="transparent", command=lambda: self._submit("")).pack(side="left")
        ctk.CTkButton(footer, text="Apply", command=self._apply).pack(side="right")

    def _apply(self):
        hour = self.hour_var.get()
        minute = self.minute_var.get()
        if hour == "--" or minute == "--":
            self._submit("")
            return
        self._submit(f"{hour}:{minute}")

    def _submit(self, value):
        if callable(self._on_select):
            self._on_select(value)
        self.destroy()


class EventTimePickerField(ctk.CTkFrame):
    def __init__(
        self,
        master,
        *,
        initial_value="",
        picker_button_text="Pick",
        now_button_text="Now",
        clear_button_text="Clear",
        empty_hint_text="No time selected",
    ):
        super().__init__(master, fg_color="transparent")
        self._empty_hint_text = empty_hint_text
        self._value_var = tk.StringVar()

        self.grid_columnconfigure(0, weight=1)

        self.entry = ctk.CTkEntry(self, textvariable=self._value_var, placeholder_text="HH:MM")
        self.entry.grid(row=0, column=0, padx=(0, 8), pady=0, sticky="ew")
        self.entry.bind("<FocusOut>", self._on_focus_out)

        controls = ctk.CTkFrame(self, fg_color="transparent")
        controls.grid(row=0, column=1, sticky="e")
        ctk.CTkButton(controls, text=picker_button_text, width=72, command=self._open_picker).pack(side="left")
        ctk.CTkButton(controls, text=now_button_text, width=64, command=self._set_now).pack(side="left", padx=6)
        ctk.CTkButton(
            controls,
            text=clear_button_text,
            width=72,
            fg_color="transparent",
            command=self.clear,
        ).pack(side="left")

        self.hint_label = ctk.CTkLabel(self, text="", anchor="w", text_color="#A8A8A8")
        self.hint_label.grid(row=1, column=0, columnspan=2, pady=(6, 0), sticky="w")

        self.set(initial_value)

    def _open_picker(self):
        EventTimePickerPopup(
            self.entry,
            initial_value=self.get(),
            on_select=lambda value: self.set(value),
        )

    def _set_now(self):
        now = datetime.now().replace(second=0, microsecond=0)
        rounded_minute = int(round(now.minute / 5.0) * 5)
        if rounded_minute == 60:
            now = now.replace(minute=0)
            hour = (now.hour + 1) % 24
            self.set(f"{hour:02d}:00")
            return
        self.set(f"{now.hour:02d}:{rounded_minute:02d}")

    def _on_focus_out(self, _event=None):
        current = self._value_var.get()
        normalized = normalize_event_time(current)
        if normalized != current.strip():
            self._value_var.set(normalized)
        self._refresh_hint()

    def _refresh_hint(self):
        value = self._value_var.get().strip()
        self.hint_label.configure(text=value if value else self._empty_hint_text)

    def clear(self):
        self._value_var.set("")
        self._refresh_hint()

    def set(self, value):
        normalized = normalize_event_time(value)
        display_value = normalized if normalized or not str(value or "").strip() else str(value).strip()
        self._value_var.set(display_value)
        self._refresh_hint()

    def get(self):
        return normalize_event_time(self._value_var.get())
