from __future__ import annotations

from typing import Callable

import customtkinter as ctk


class TimerControlWindow(ctk.CTkToplevel):
    def __init__(
        self,
        parent,
        on_start: Callable[[], None],
        on_stop: Callable[[], None],
        on_pause: Callable[[], None],
        on_continue: Callable[[], None],
        on_remove_minute: Callable[[], None],
        on_add_minute: Callable[[], None],
        on_close: Callable[[], None],
    ):
        super().__init__(parent)
        self.title("Timer Controls")
        self.geometry("280x155")
        self.resizable(False, False)
        self.attributes("-topmost", True)
        self.protocol("WM_DELETE_WINDOW", on_close)

        frame = ctk.CTkFrame(self)
        frame.pack(fill="both", expand=True, padx=8, pady=8)

        self.time_var = ctk.StringVar(value="05:00")
        ctk.CTkEntry(frame, textvariable=self.time_var, justify="center").pack(fill="x", pady=(0, 6))

        row1 = ctk.CTkFrame(frame, fg_color="transparent")
        row1.pack(fill="x", pady=2)
        ctk.CTkButton(row1, text="Start", command=on_start, width=60).pack(side="left", expand=True, padx=2)
        ctk.CTkButton(row1, text="Stop", command=on_stop, width=60).pack(side="left", expand=True, padx=2)

        row2 = ctk.CTkFrame(frame, fg_color="transparent")
        row2.pack(fill="x", pady=2)
        ctk.CTkButton(row2, text="-1 min", command=on_remove_minute, width=60).pack(side="left", expand=True, padx=2)
        ctk.CTkButton(row2, text="+1 min", command=on_add_minute, width=60).pack(side="left", expand=True, padx=2)

        row3 = ctk.CTkFrame(frame, fg_color="transparent")
        row3.pack(fill="x", pady=2)
        ctk.CTkButton(row3, text="Pause", command=on_pause, width=60).pack(side="left", expand=True, padx=2)
        ctk.CTkButton(row3, text="Continue", command=on_continue, width=60).pack(side="left", expand=True, padx=2)

    def show(self) -> None:
        self.deiconify()
        self.lift()
        self.focus_force()
