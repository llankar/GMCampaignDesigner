from __future__ import annotations

import tkinter as tk
from typing import Any


class TourOverlay:
    """Visual overlay helper used to focus/highlight a target widget."""

    def __init__(self, root: Any) -> None:
        self._root = root
        self._current_target: Any = None
        self._overlay_window: tk.Toplevel | None = None
        self._canvas: tk.Canvas | None = None
        self._configure_bind = self._root.bind("<Configure>", self._on_configure, add="+")

    def show_highlight(self, target_widget: Any) -> None:
        self._current_target = target_widget
        self._ensure_overlay()
        self.refresh_geometry()

    def clear(self) -> None:
        self._current_target = None
        if self._overlay_window is not None:
            self._overlay_window.withdraw()

    def refresh_geometry(self) -> None:
        if self._current_target is None:
            return

        root_updater = getattr(self._root, "update_idletasks", None)
        if callable(root_updater):
            root_updater()

        target_updater = getattr(self._current_target, "update_idletasks", None)
        if callable(target_updater):
            target_updater()

        if self._overlay_window is None or self._canvas is None:
            return

        try:
            x = int(self._current_target.winfo_rootx())
            y = int(self._current_target.winfo_rooty())
            width = int(self._current_target.winfo_width())
            height = int(self._current_target.winfo_height())
        except tk.TclError:
            self.clear()
            return

        if width <= 1 or height <= 1:
            self._overlay_window.withdraw()
            return

        pad = 4
        self._overlay_window.deiconify()
        self._overlay_window.geometry(f"{width + (pad * 2)}x{height + (pad * 2)}+{x - pad}+{y - pad}")
        self._canvas.configure(width=width + (pad * 2), height=height + (pad * 2))
        self._canvas.delete("highlight")
        self._canvas.create_rectangle(
            pad,
            pad,
            width + pad,
            height + pad,
            outline="#5CC8FF",
            width=3,
            tags="highlight",
        )

    def _ensure_overlay(self) -> None:
        if self._overlay_window is not None and self._canvas is not None:
            return
        if getattr(self._root, "tk", None) is None:
            return

        self._overlay_window = tk.Toplevel(self._root)
        self._overlay_window.overrideredirect(True)
        self._overlay_window.attributes("-topmost", True)
        self._overlay_window.configure(bg="magenta")
        self._overlay_window.wm_attributes("-transparentcolor", "magenta")

        self._canvas = tk.Canvas(
            self._overlay_window,
            highlightthickness=0,
            borderwidth=0,
            bg="magenta",
        )
        self._canvas.pack(fill="both", expand=True)

    def _on_configure(self, _event: Any) -> None:
        self.refresh_geometry()
