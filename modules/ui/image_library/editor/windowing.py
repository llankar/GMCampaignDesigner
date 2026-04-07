"""Window-behavior helpers for image editor dialogs."""

from __future__ import annotations

import tkinter as tk


def apply_startup_window_mode(window: tk.Misc) -> None:
    """Try to open maximized, fallback to full-screen geometry on unsupported platforms."""
    try:
        window.state("zoomed")
        return
    except Exception:
        pass

    try:
        width = max(int(window.winfo_screenwidth() or 0), 1024)
        height = max(int(window.winfo_screenheight() or 0), 768)
        window.geometry(f"{width}x{height}+0+0")
    except Exception:
        # Keep default geometry if screen metrics are unavailable in tests/headless runtimes.
        return

