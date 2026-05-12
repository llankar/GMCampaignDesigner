"""Scenario status field resolution helpers."""
from __future__ import annotations

from typing import Any

from modules.campaigns.shared.arc_status import DEFAULT_SCENARIO_STATUS, canonicalize_scenario_status

_SCENARIO_STATUS_KEYS = (
    "Status",
    "status",
    "Statut",
    "statut",
    "ScenarioStatus",
    "scenario_status",
)


def read_scenario_status(scenario: Any, default: str = DEFAULT_SCENARIO_STATUS) -> str:
    """Return the canonical status from a scenario object or mapping.

    Scenario records can come from generic editor dictionaries, generated payloads,
    or dataclass-like dashboard payloads. Older/custom records may also carry a
    localized ``Statut`` key, so resolve all known aliases before applying the
    canonical campaign status rules.
    """
    raw_status = _read_raw_status(scenario)
    return canonicalize_scenario_status(raw_status, default=default)


def _read_raw_status(scenario: Any) -> Any:
    """Read the first non-empty status-like value from supported scenario shapes."""
    if scenario is None:
        return None

    if isinstance(scenario, dict):
        for key in _SCENARIO_STATUS_KEYS:
            value = scenario.get(key)
            if _has_value(value):
                return value
        return None

    for attr_name in ("status", "Status", "statut", "Statut", "scenario_status"):
        value = getattr(scenario, attr_name, None)
        if _has_value(value):
            return value

    return None


def _has_value(value: Any) -> bool:
    """Return whether a status candidate contains a meaningful value."""
    return str(value or "").strip() != ""
