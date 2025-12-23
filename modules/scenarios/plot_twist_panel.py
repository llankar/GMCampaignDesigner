from __future__ import annotations

from datetime import datetime
from typing import Optional

import customtkinter as ctk
from tkinter import messagebox

from modules.helpers.logging_helper import log_exception, log_module_import, log_methods
from modules.helpers.plot_twist_helper import load_plot_twists_table, roll_plot_twist


@log_methods
class PlotTwistPanel(ctk.CTkFrame):
    def __init__(self, master=None, **kwargs):
        super().__init__(master, **kwargs)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)
        self.rowconfigure(4, weight=2)

        self._table: Optional[dict] = None
        self._build_ui()
        self._load_table()

    def _build_ui(self) -> None:
        header = ctk.CTkFrame(self)
        header.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 4))
        header.columnconfigure(1, weight=1)

        ctk.CTkLabel(header, text="Plot Twists", font=("Segoe UI", 16, "bold")).grid(
            row=0, column=0, sticky="w"
        )
        self.table_title_var = ctk.StringVar(value="-")
        ctk.CTkLabel(header, textvariable=self.table_title_var).grid(row=0, column=1, sticky="w", padx=(6, 0))

        self.roll_button = ctk.CTkButton(header, text="Roll Plot Twist", command=self.roll_plot_twist)
        self.roll_button.grid(row=0, column=2, sticky="e")

        meta = ctk.CTkFrame(self)
        meta.grid(row=1, column=0, sticky="ew", padx=8, pady=(0, 6))
        meta.columnconfigure(1, weight=1)

        ctk.CTkLabel(meta, text="Dice:").grid(row=0, column=0, sticky="w")
        self.dice_var = ctk.StringVar(value="-")
        ctk.CTkLabel(meta, textvariable=self.dice_var).grid(row=0, column=1, sticky="w")

        ctk.CTkLabel(meta, text="Description:").grid(row=1, column=0, sticky="nw", pady=(4, 0))
        self.description_box = ctk.CTkTextbox(meta, height=70, wrap="word")
        self.description_box.grid(row=1, column=1, sticky="ew", pady=(4, 0))
        self.description_box.configure(state="disabled")

        result_frame = ctk.CTkFrame(self)
        result_frame.grid(row=2, column=0, sticky="nsew", padx=8, pady=(0, 6))
        result_frame.rowconfigure(1, weight=1)
        result_frame.columnconfigure(0, weight=1)

        ctk.CTkLabel(result_frame, text="Latest Twist").grid(row=0, column=0, sticky="w")
        self.result_box = ctk.CTkTextbox(result_frame, height=90, wrap="word")
        self.result_box.grid(row=1, column=0, sticky="nsew", pady=(4, 0))
        self.result_box.configure(state="disabled")

        history_frame = ctk.CTkFrame(self)
        history_frame.grid(row=4, column=0, sticky="nsew", padx=8, pady=(0, 8))
        history_frame.rowconfigure(1, weight=1)
        history_frame.columnconfigure(0, weight=1)

        ctk.CTkLabel(history_frame, text="History").grid(row=0, column=0, sticky="w")
        self.history_box = ctk.CTkTextbox(history_frame, wrap="word", height=150)
        self.history_box.grid(row=1, column=0, sticky="nsew")
        self.history_box.configure(state="disabled")

    def _load_table(self) -> None:
        self._table = load_plot_twists_table()
        if not self._table:
            self.table_title_var.set("Plot twists table not found")
            self.dice_var.set("-")
            self._set_description("")
            self.roll_button.configure(state="disabled")
            return
        self.table_title_var.set(self._table.get("title") or "Plot Twists")
        self.dice_var.set(self._table.get("dice") or "-")
        self._set_description(self._table.get("description") or "")
        self.roll_button.configure(state="normal")

    def _set_description(self, text: str) -> None:
        self.description_box.configure(state="normal")
        self.description_box.delete("1.0", "end")
        if text:
            self.description_box.insert("end", text)
        self.description_box.configure(state="disabled")

    def _set_result(self, text: str) -> None:
        self.result_box.configure(state="normal")
        self.result_box.delete("1.0", "end")
        if text:
            self.result_box.insert("end", text)
        self.result_box.configure(state="disabled")

    def _append_history(self, text: str) -> None:
        self.history_box.configure(state="normal")
        self.history_box.insert("end", text + "\n")
        self.history_box.see("end")
        self.history_box.configure(state="disabled")

    def roll_plot_twist(self) -> None:
        try:
            result = roll_plot_twist()
        except Exception as exc:
            log_exception(exc, func_name="PlotTwistPanel.roll_plot_twist")
            messagebox.showerror("Plot Twists", f"Unable to roll plot twist: {exc}")
            return
        if not result:
            messagebox.showwarning("Plot Twists", "Plot twists table is unavailable.")
            return

        text = f"{result.get('table')}: {result.get('roll')} -> {result.get('result')}"
        self._set_result(text)
        timestamp = datetime.now().strftime("%H:%M:%S")
        self._append_history(f"[{timestamp}] {text}")


log_module_import(__name__)

__all__ = ["PlotTwistPanel"]
