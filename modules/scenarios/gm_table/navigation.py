"""Navigation helpers for opening scenarios on the primary GM Table."""

from __future__ import annotations

from typing import Any


def find_gm_table_launcher(widget: Any) -> Any | None:
    """Return the nearest widget/root exposing the GM Table launcher API."""
    current = widget
    visited: set[int] = set()
    while current is not None and id(current) not in visited:
        visited.add(id(current))
        if callable(getattr(current, "open_gm_table", None)):
            return current
        current = getattr(current, "master", None)
    return None


def open_scenario_in_main_gm_table(widget: Any, scenario_name: str) -> bool:
    """Open *scenario_name* in a Scenario Board on the primary GM Table."""
    launcher = find_gm_table_launcher(widget)
    if launcher is None:
        return False
    launcher.open_gm_table(scenario_name=scenario_name)
    return True
