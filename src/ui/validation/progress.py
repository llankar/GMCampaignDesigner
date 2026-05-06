"""Lightweight progress window for campaign validation scans."""

from __future__ import annotations

from typing import Any


class ValidationScanProgress:
    """Tiny, best-effort progress dialog that reports validation phases.

    The launcher performs a short synchronous scan before the issue wizard opens.
    This helper keeps the UI responsive enough to show the current phase without
    adding background-thread complexity. Tests and headless contexts receive a
    no-op object when the master is not a Tk widget.
    """

    def __init__(self, master: Any, *, title: str = "Validation") -> None:
        self.master = master
        self.title = title
        self.window: Any | None = None
        self._phase_label: Any | None = None

    def show(self, phase: str) -> "ValidationScanProgress":
        """Display the progress window if a Tk master is available."""

        if not hasattr(self.master, "tk"):
            return self

        import tkinter as tk

        window = tk.Toplevel(self.master)
        self.window = window
        window.title(self.title)
        window.transient(self.master)
        window.resizable(False, False)

        frame = tk.Frame(window, padx=18, pady=16)
        frame.grid(row=0, column=0, sticky="nsew")
        tk.Label(
            frame,
            text="Validation de campagne",
            font=("TkDefaultFont", 12, "bold"),
        ).grid(row=0, column=0, sticky="w", pady=(0, 8))
        self._phase_label = tk.Label(frame, text=phase, anchor="w")
        self._phase_label.grid(row=1, column=0, sticky="ew")
        window.update_idletasks()
        return self

    def set_phase(self, phase: str) -> None:
        """Update the visible phase text, if the window exists."""

        if self._phase_label is not None:
            self._phase_label.configure(text=phase)
        if self.window is not None:
            self.window.update_idletasks()

    def close(self) -> None:
        """Close the progress window if it was displayed."""

        if self.window is not None:
            self.window.destroy()
            self.window = None
            self._phase_label = None
