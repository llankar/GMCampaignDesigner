"""Thin wrapper to keep tooltip usage consistent in dock widgets."""

from __future__ import annotations

from modules.ui.tooltip import ToolTip


def attach_tooltip(widget, text: str, delay: int = 350) -> ToolTip:
    """Attach a shared tooltip implementation to any widget."""
    return ToolTip(widget, text=text, delay=delay)
