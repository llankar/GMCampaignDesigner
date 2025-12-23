from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Optional

import customtkinter as ctk

from modules.dice import dice_engine
from modules.helpers.logging_helper import log_exception, log_info, log_methods, log_module_import
from modules.helpers.random_table_loader import PLOT_TWIST_TABLE_ID, load_plot_twist_table

log_module_import(__name__)


@dataclass(frozen=True)
class PlotTwistResult:
    table: str
    roll: int
    result: str
    timestamp: datetime

    @property
    def timestamp_label(self) -> str:
        return self.timestamp.strftime("%Y-%m-%d %H:%M:%S")

    def to_payload(self) -> dict:
        return {
            "table": self.table,
            "roll": self.roll,
            "result": self.result,
            "timestamp": self.timestamp_label,
        }


_latest_result: Optional[PlotTwistResult] = None
_listeners: list[Callable[[PlotTwistResult], None]] = []
_table_cache: Optional[dict] = None


def _load_plot_twist_table() -> Optional[dict]:
    global _table_cache
    if _table_cache:
        return _table_cache
    table = load_plot_twist_table(PLOT_TWIST_TABLE_ID)
    _table_cache = table
    return table


def _match_entry(table: dict, value: int) -> dict:
    for entry in table.get("entries", []):
        if entry.get("min", 0) <= value <= entry.get("max", 0):
            return entry
    return table.get("entries", [{}])[0] if table.get("entries") else {"result": "(no entries)"}


def add_plot_twist_listener(listener: Callable[[PlotTwistResult], None]) -> None:
    if listener in _listeners:
        return
    _listeners.append(listener)


def remove_plot_twist_listener(listener: Callable[[PlotTwistResult], None]) -> None:
    try:
        _listeners.remove(listener)
    except ValueError:
        pass


def _notify_listeners(result: PlotTwistResult) -> None:
    for listener in list(_listeners):
        try:
            listener(result)
        except Exception as exc:
            log_exception(exc, func_name="plot_twist_panel._notify_listeners")


def get_latest_plot_twist() -> Optional[PlotTwistResult]:
    return _latest_result


def roll_plot_twist() -> PlotTwistResult:
    global _latest_result
    table = _load_plot_twist_table() or {}
    try:
        roll = dice_engine.roll_formula(table.get("dice", "1d20"))
        roll_total = roll.total
    except Exception as exc:
        log_exception(exc, func_name="plot_twist_panel.roll_plot_twist")
        roll_total = 0
    entry = _match_entry(table, roll_total) if table else {"result": "(no entries)"}
    result = PlotTwistResult(
        table=table.get("title") or "Plot Twist",
        roll=roll_total,
        result=entry.get("result", "(no entries)"),
        timestamp=datetime.now(),
    )
    _latest_result = result
    _notify_listeners(result)
    log_info("Plot twist rolled.", func_name="plot_twist_panel.roll_plot_twist")
    return result


@log_methods
class PlotTwistPanel(ctk.CTkFrame):
    def __init__(self, master=None, *, compact: bool = False, show_title: bool = True, **kwargs):
        super().__init__(master, **kwargs)
        self._compact = compact
        self.columnconfigure(0, weight=1)

        title_font = ("Segoe UI", 15, "bold")
        body_font = ("Segoe UI", 13 if compact else 14)
        meta_font = ("Segoe UI", 11 if compact else 12)
        wraplength = 280 if compact else 420

        if show_title:
            title_label = ctk.CTkLabel(self, text="Plot Twist", font=title_font)
            title_label.grid(row=0, column=0, sticky="w", padx=6, pady=(2, 6))
            row_offset = 1
        else:
            row_offset = 0

        self.result_var = ctk.StringVar(value="No plot twist rolled yet.")
        self.result_label = ctk.CTkLabel(
            self,
            textvariable=self.result_var,
            wraplength=wraplength,
            justify="left",
            font=body_font,
        )
        self.result_label.grid(row=row_offset, column=0, sticky="ew", padx=6, pady=(0, 4))

        self.meta_var = ctk.StringVar(value="")
        self.meta_label = ctk.CTkLabel(self, textvariable=self.meta_var, font=meta_font, text_color="#A3ADC2")
        self.meta_label.grid(row=row_offset + 1, column=0, sticky="w", padx=6, pady=(0, 8))

        button_row = ctk.CTkFrame(self, fg_color="transparent")
        button_row.grid(row=row_offset + 2, column=0, sticky="ew", padx=6, pady=(0, 4))
        button_row.columnconfigure(0, weight=1)

        self.roll_button = ctk.CTkButton(button_row, text="Roll another", command=self.roll_another)
        self.roll_button.grid(row=0, column=0, sticky="w")

        add_plot_twist_listener(self._on_plot_twist_update)
        self.bind("<Destroy>", self._on_destroy, add="+")
        self._sync_latest()

    def _on_destroy(self, _event=None) -> None:
        remove_plot_twist_listener(self._on_plot_twist_update)

    def _sync_latest(self) -> None:
        result = get_latest_plot_twist()
        if result:
            self._apply_result(result)

    def _apply_result(self, result: PlotTwistResult) -> None:
        self.result_var.set(result.result)
        self.meta_var.set(f"{result.table} · Roll {result.roll} · {result.timestamp_label}")

    def _on_plot_twist_update(self, result: PlotTwistResult) -> None:
        self._apply_result(result)

    def roll_another(self) -> None:
        result = roll_plot_twist()
        self._apply_result(result)
