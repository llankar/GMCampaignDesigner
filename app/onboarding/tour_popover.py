from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any, Callable

from .tour_models import TourPlacement, TourStep


class TourPopover:
    """Text card + navigation controls for a tour step."""

    def __init__(
        self,
        root: Any,
        on_next: Callable[[], None],
        on_prev: Callable[[], None],
        on_close: Callable[[], None],
    ) -> None:
        self._root = root
        self._on_next = on_next
        self._on_prev = on_prev
        self._on_close = on_close
        self._visible = False
        self._target_widget: Any = None
        self._step: TourStep | None = None

        self._window: tk.Toplevel | None = None
        self._title_var: tk.StringVar | None = None
        self._description_var: tk.StringVar | None = None

        self._configure_bind = self._root.bind("<Configure>", self._on_configure, add="+")

    def show(self, step: TourStep, target_widget: Any) -> None:
        self._ensure_window()
        self._visible = True
        self._step = step
        self._target_widget = target_widget
        if self._title_var is not None:
            self._title_var.set(step.title)
        if self._description_var is not None:
            self._description_var.set(step.description)

        if self._window is not None:
            self._window.deiconify()
            self._window.lift()
        self.refresh_geometry()

    def hide(self) -> None:
        self._visible = False
        self._target_widget = None
        self._step = None
        if self._window is not None:
            self._window.withdraw()

    def refresh_geometry(self) -> None:
        if not self._visible or self._target_widget is None or self._window is None:
            return

        root_updater = getattr(self._root, "update_idletasks", None)
        if callable(root_updater):
            root_updater()

        target_updater = getattr(self._target_widget, "update_idletasks", None)
        if callable(target_updater):
            target_updater()

        self._window.update_idletasks()

        try:
            tx = int(self._target_widget.winfo_rootx())
            ty = int(self._target_widget.winfo_rooty())
            tw = int(self._target_widget.winfo_width())
            th = int(self._target_widget.winfo_height())
        except tk.TclError:
            self.hide()
            return

        ww = self._window.winfo_width()
        wh = self._window.winfo_height()
        gap = 12
        placement = self._step.placement if self._step else TourPlacement.BOTTOM

        if placement == TourPlacement.TOP:
            x = tx + (tw - ww) // 2
            y = ty - wh - gap
        elif placement == TourPlacement.LEFT:
            x = tx - ww - gap
            y = ty + (th - wh) // 2
        elif placement == TourPlacement.RIGHT:
            x = tx + tw + gap
            y = ty + (th - wh) // 2
        else:
            x = tx + (tw - ww) // 2
            y = ty + th + gap

        screen_w = self._root.winfo_screenwidth()
        screen_h = self._root.winfo_screenheight()
        x = max(8, min(x, screen_w - ww - 8))
        y = max(8, min(y, screen_h - wh - 8))
        self._window.geometry(f"+{x}+{y}")

    def _ensure_window(self) -> None:
        if self._window is not None:
            return
        if getattr(self._root, "tk", None) is None:
            return

        self._window = tk.Toplevel(self._root)
        self._window.withdraw()
        self._window.overrideredirect(True)
        self._window.attributes("-topmost", True)
        self._title_var = tk.StringVar(master=self._window, value="")
        self._description_var = tk.StringVar(master=self._window, value="")

        card = ttk.Frame(self._window, padding=12, relief="solid", borderwidth=1)
        card.grid(row=0, column=0, sticky="nsew")

        title = ttk.Label(card, textvariable=self._title_var, font=("TkDefaultFont", 11, "bold"))
        title.grid(row=0, column=0, columnspan=3, sticky="w")

        desc = ttk.Label(card, textvariable=self._description_var, wraplength=300, justify="left")
        desc.grid(row=1, column=0, columnspan=3, sticky="w", pady=(8, 12))

        prev_button = ttk.Button(card, text="Back", command=self._on_prev)
        prev_button.grid(row=2, column=0, sticky="w")

        next_button = ttk.Button(card, text="Next", command=self._on_next)
        next_button.grid(row=2, column=1, sticky="w", padx=(8, 0))

        close_button = ttk.Button(card, text="Close", command=self._on_close)
        close_button.grid(row=2, column=2, sticky="e", padx=(8, 0))

    def _on_configure(self, _event: Any) -> None:
        self.refresh_geometry()
