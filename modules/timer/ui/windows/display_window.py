from __future__ import annotations

from typing import Callable, Optional

import customtkinter as ctk


class TimerDisplayWindow(ctk.CTkToplevel):
    def __init__(
        self,
        parent,
        on_open_controls: Optional[Callable[[], None]] = None,
        on_delete_timer: Optional[Callable[[], None]] = None,
    ):
        super().__init__(parent)
        self._drag_offset_x = 0
        self._on_open_controls = on_open_controls
        self._on_delete_timer = on_delete_timer
        self._drag_offset_y = 0
        self._blink_job = None
        self._blink_state = False

        self.title("Timer")
        self.geometry("260x116")
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
            font=("Consolas", 20, "bold"),
        )
        self._clock_label.pack(fill="both", expand=True, pady=(0, 6))

        self._delete_button = ctk.CTkButton(
            container,
            text="Delete",
            width=80,
            command=self._delete_timer,
        )
        self._delete_button.pack(pady=(0, 2))

        self._bind_dragging(container)
        self._bind_dragging(self._clock_label)
        self._bind_open_controls(container)
        self._bind_open_controls(self._clock_label)

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

    def _bind_open_controls(self, widget) -> None:
        widget.bind("<Double-Button-1>", self._on_open_controls_requested)

    def _on_open_controls_requested(self, _event) -> None:
        if self._on_open_controls is not None:
            self._on_open_controls()

    def _delete_timer(self) -> None:
        if self._on_delete_timer is not None:
            self._on_delete_timer()

    def set_time(self, text: str) -> None:
        self._clock_label.configure(text=text)

    def start_finished_blink(self) -> None:
        if self._blink_job is not None:
            return
        self._blink_state = False
        self._run_blink()

    def stop_finished_blink(self) -> None:
        if self._blink_job is not None:
            self.after_cancel(self._blink_job)
            self._blink_job = None
        self._clock_label.configure(text_color="#ff2b2b")

    def _run_blink(self) -> None:
        self._blink_state = not self._blink_state
        color = "#ffffff" if self._blink_state else "#ff2b2b"
        self._clock_label.configure(text_color=color)
        self._blink_job = self.after(420, self._run_blink)

    def show(self) -> None:
        self.deiconify()
        self.lift()

    def hide(self) -> None:
        self.stop_finished_blink()
        self.withdraw()
