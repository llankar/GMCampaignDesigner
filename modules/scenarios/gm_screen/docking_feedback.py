"""Docking UI copy + visual feedback helpers for GM screen tabs."""

from __future__ import annotations

import customtkinter as ctk


DOCK_BADGE_COPY = {
    True: ("Floating", "#7F1D1D", "#FEE2E2"),
    False: ("Docked", "#14532D", "#DCFCE7"),
}


def dock_toggle_text(is_detached: bool) -> str:
    """Return compact CTA copy for the dock toggle button."""
    return "Dock" if is_detached else "Float"


def dock_toggle_tooltip(is_detached: bool) -> str:
    """Return tooltip copy with shortcut hints."""
    action = "Dock this panel" if is_detached else "Float this panel"
    return (
        f"{action}\n"
        "• Double-click header to float\n"
        "• Ctrl+Shift+Click to dock all floating panels"
    )


def apply_origin_highlight(frame, scheduler, *, hold_ms: int = 1400) -> None:
    """Highlight origin tab after undocking for orientation feedback."""
    if frame is None or not _alive(frame):
        return
    try:
        original_border = frame.cget("border_color")
        original_width = int(float(frame.cget("border_width")))
    except Exception:
        return
    frame.configure(border_color="#F59E0B", border_width=max(2, original_width + 1))

    def _restore():
        if not _alive(frame):
            return
        frame.configure(border_color=original_border, border_width=original_width)

    scheduler(hold_ms, _restore)


def pulse_slot(frame, scheduler, *, pulses: int = 2, frame_ms: int = 120) -> None:
    """Pulse tab slot border to confirm redocking placement."""
    if frame is None or not _alive(frame):
        return
    try:
        base_border = frame.cget("border_color")
    except Exception:
        return
    colors = [base_border, "#22C55E", base_border, "#4ADE80", base_border]
    steps = min(len(colors), (pulses * 2) + 1)

    def _tick(index: int = 0):
        if not _alive(frame):
            return
        frame.configure(border_color=colors[index])
        if index + 1 < steps:
            scheduler(frame_ms, lambda: _tick(index + 1))

    _tick(0)


def _alive(widget) -> bool:
    try:
        return bool(widget.winfo_exists())
    except Exception:
        return False

