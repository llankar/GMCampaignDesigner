from __future__ import annotations

import tkinter as tk
from typing import Optional

import customtkinter as ctk


class TimerAlerts:
    """Visual and optional sound alerts for finished timers."""

    def __init__(self, parent: tk.Misc, sound_enabled: bool = True) -> None:
        self._parent = parent
        self._sound_enabled = bool(sound_enabled)
        self._active_banner: Optional[ctk.CTkToplevel] = None

    def set_sound_enabled(self, enabled: bool) -> None:
        self._sound_enabled = bool(enabled)

    def notify_finished(self, timer_name: str) -> None:
        self._show_banner(timer_name)
        if self._sound_enabled:
            self._play_sound()

    def _play_sound(self) -> None:
        try:
            self._parent.bell()
        except Exception:
            pass

    def _show_banner(self, timer_name: str) -> None:
        if self._active_banner is not None:
            try:
                self._active_banner.destroy()
            except Exception:
                pass

        top = ctk.CTkToplevel(self._parent)
        top.title("Timer Alert")
        top.geometry("380x110")
        top.attributes("-topmost", True)

        ctk.CTkLabel(top, text="⏰ Timer finished", font=("Segoe UI", 18, "bold")).pack(pady=(16, 4))
        ctk.CTkLabel(top, text=timer_name or "Timer", font=("Segoe UI", 14)).pack(pady=(0, 8))
        ctk.CTkButton(top, text="Dismiss", command=top.destroy).pack(pady=(0, 12))

        self._active_banner = top
        top.after(5500, lambda: top.winfo_exists() and top.destroy())
