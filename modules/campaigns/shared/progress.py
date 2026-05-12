"""Progress calculations shared by campaign advancement UI."""
from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from modules.campaigns.shared.arc_status import CANONICAL_PROGRESS_STATUSES, canonicalize_scenario_status
from modules.campaigns.shared.scenario_status import read_scenario_status

_PLANNED, _IN_PROGRESS, _PAUSED, _COMPLETED = CANONICAL_PROGRESS_STATUSES
_STATUS_PROGRESS = {
    _PLANNED: 0.0,
    _IN_PROGRESS: 0.5,
    _PAUSED: 0.5,
    _COMPLETED: 1.0,
}


def status_progress(status: object) -> float:
    """Return normalized progress for a scenario-like status value."""
    return _STATUS_PROGRESS[canonicalize_scenario_status(status)]


def arc_progress_from_scenarios(scenarios: Iterable[Any] | None) -> float:
    """Return an arc's advancement as the average progress of linked scenarios."""
    scenario_list = list(scenarios or [])
    if not scenario_list:
        return 0.0
    return sum(status_progress(read_scenario_status(scenario)) for scenario in scenario_list) / len(scenario_list)


def campaign_progress_from_arcs(arcs: Iterable[Any] | None) -> float:
    """Return campaign advancement as the average advancement of its arcs."""
    arc_list = list(arcs or [])
    if not arc_list:
        return 0.0
    return sum(arc_progress_from_scenarios(_read_scenarios(arc)) for arc in arc_list) / len(arc_list)


def _read_scenarios(arc: Any) -> Iterable[Any] | None:
    """Read scenarios from either a dataclass-style object or a dictionary."""
    if isinstance(arc, dict):
        return arc.get("scenarios") or arc.get("Scenarios")
    return getattr(arc, "scenarios", None)
