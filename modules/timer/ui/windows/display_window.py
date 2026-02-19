from __future__ import annotations

import customtkinter as ctk


class TimerDisplayWindow(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Timer")
        self.geometry("260x90")
        self.resizable(False, False)
        self.attributes("-topmost", True)
        self.configure(fg_color="#010101")

        try:
            self.wm_attributes("-transparentcolor", "#010101")
        except Exception:
            self.attributes("-alpha", 0.85)

        container = ctk.CTkFrame(self, fg_color="#010101")
        container.pack(fill="both", expand=True, padx=6, pady=6)

        self._clock_label = ctk.CTkLabel(
            container,
            text="00:00:00",
            text_color="#ff2b2b",
            font=("Consolas", 44, "bold"),
        )
        self._clock_label.pack(fill="both", expand=True)

    def set_time(self, text: str) -> None:
        self._clock_label.configure(text=text)

    def show(self) -> None:
        self.deiconify()
        self.lift()

    def hide(self) -> None:
        self.withdraw()
