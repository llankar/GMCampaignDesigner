"""Routing helpers for campaign GM screen."""

from __future__ import annotations

from typing import Callable


def open_scenario_in_embedded_gm_screen(widget, scenario_name: str, *, fallback: Callable[[], None]) -> None:
    """Prefer the host application's embedded GM screen when available."""

    host = getattr(widget, "winfo_toplevel", lambda: None)()
    open_gm_screen = getattr(host, "open_gm_screen", None)
    if callable(open_gm_screen):
        open_gm_screen(show_empty_message=True, scenario_name=scenario_name)
        return
    fallback()
