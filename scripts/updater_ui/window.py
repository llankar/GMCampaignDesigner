"""Window for updater UI."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk


class UpdaterWindow:
    def __init__(self) -> None:
        """Initialize the UpdaterWindow instance."""
        self.root = tk.Tk()
        self.root.title("GMCampaignDesigner - Updater")
        self.root.geometry("520x180")
        self.root.resizable(False, False)
        self.root.attributes("-topmost", True)

        self._busy = True
        self._build_widgets()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close_request)

    def _build_widgets(self) -> None:
        """Build widgets."""
        container = ttk.Frame(self.root, padding=14)
        container.pack(fill="both", expand=True)

        self.status_var = tk.StringVar(value="Preparing update…")
        ttk.Label(container, textvariable=self.status_var, anchor="w").pack(fill="x", pady=(0, 12))

        self.progress_var = tk.DoubleVar(value=0.0)
        self.progressbar = ttk.Progressbar(
            container,
            orient="horizontal",
            mode="determinate",
            maximum=100,
            variable=self.progress_var,
        )
        self.progressbar.pack(fill="x")

        self.details_var = tk.StringVar(value="Please wait while the update is being applied.")
        ttk.Label(container, textvariable=self.details_var, anchor="w", foreground="#555555").pack(fill="x", pady=(10, 0))

    def _on_close_request(self) -> None:
        """Handle close request."""
        if self._busy:
            self.details_var.set("Update in progress: closing is disabled to avoid corruption.")
            self.root.bell()
            return
        self.root.destroy()

    def set_busy(self, busy: bool) -> None:
        """Set busy."""
        self._busy = busy

    def set_progress(self, message: str, fraction: float) -> None:
        """Set progress."""
        self.status_var.set(message)
        self.progress_var.set(max(0.0, min(100.0, float(fraction) * 100.0)))

    def show_success(self) -> None:
        """Show success."""
        self._busy = False
        self.status_var.set("Update complete")
        self.details_var.set("You can close this window.")

    def show_error(self, message: str) -> None:
        """Show error."""
        self._busy = False
        self.status_var.set("Update failed")
        self.details_var.set(message)

    def run(self) -> None:
        """Run the operation."""
        self.root.mainloop()
