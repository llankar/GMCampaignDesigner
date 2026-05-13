"""Progress calculations shared by campaign advancement UI."""
from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from modules.campaigns.shared.arc_status import CANONICAL_PROGRESS_STATUSES, canonicalize_scenario_status
from modules.campaigns.shared.scenario_status import read_scenario_status

_COMPLETED = CANONICAL_PROGRESS_STATUSES[-1]


def status_progress(status: object) -> float:
    """Return completion progress for a scenario-like status value."""
    return 1.0 if canonicalize_scenario_status(status) == _COMPLETED else 0.0


def arc_progress_from_scenarios(scenarios: Iterable[Any] | None) -> float:
    """Return an arc's advancement as completed linked scenarios over all linked scenarios."""
    scenario_list = list(scenarios or [])
    if not scenario_list:
        return 0.0
    return sum(status_progress(read_scenario_status(scenario)) for scenario in scenario_list) / len(scenario_list)


def campaign_progress_from_arcs(arcs: Iterable[Any] | None) -> float:
    """Return campaign advancement as completed linked scenarios over all linked scenarios."""
    total_scenarios = 0
    completed_scenarios = 0.0
    for arc in arcs or []:
        for scenario in _read_scenarios(arc) or []:
            total_scenarios += 1
            completed_scenarios += status_progress(read_scenario_status(scenario))
    if total_scenarios == 0:
        return 0.0
    return completed_scenarios / total_scenarios


def _read_scenarios(arc: Any) -> Iterable[Any] | None:
    """Read scenarios from either a dataclass-style object or a dictionary."""
    if isinstance(arc, dict):
        return arc.get("scenarios") or arc.get("Scenarios")
    return getattr(arc, "scenarios", None)
