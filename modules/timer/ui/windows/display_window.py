from __future__ import annotations

import customtkinter as ctk


class TimerDisplayWindow(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self._drag_offset_x = 0
        self._drag_offset_y = 0

        self.title("Timer")
        self.geometry("260x90")
        self.resizable(False, False)
        self.overrideredirect(True)
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

        self._bind_dragging(container)
        self._bind_dragging(self._clock_label)

    def _bind_dragging(self, widget) -> None:
        widget.bind("<ButtonPress-1>", self._on_drag_start)
        widget.bind("<B1-Motion>", self._on_drag_motion)

    def _on_drag_start(self, event) -> None:
        self._drag_offset_x = event.x_root - self.winfo_x()
        self._drag_offset_y = event.y_root - self.winfo_y()

    def _on_drag_motion(self, event) -> None:
        new_x = event.x_root - self._drag_offset_x
        new_y = event.y_root - self._drag_offset_y
        self.geometry(f"+{new_x}+{new_y}")

    def set_time(self, text: str) -> None:
        self._clock_label.configure(text=text)

    def show(self) -> None:
        self.deiconify()
        self.lift()

    def hide(self) -> None:
        self.withdraw()
