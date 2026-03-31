"""Normalization helpers for campaign forge."""
from __future__ import annotations

from typing import Any

from modules.helpers.text_helpers import deserialize_possible_json


def coerce_foundation(foundation: dict[str, Any] | None) -> dict[str, Any]:
    """Coerce foundation."""
    raw = foundation if isinstance(foundation, dict) else {}
    normalized = {
        "name": str(raw.get("name") or "").strip(),
        "genre": str(raw.get("genre") or "").strip(),
        "tone": str(raw.get("tone") or "").strip(),
        "status": str(raw.get("status") or "").strip(),
        "logline": str(raw.get("logline") or "").strip(),
        "setting": str(raw.get("setting") or "").strip(),
        "main_objective": str(raw.get("main_objective") or "").strip(),
        "stakes": str(raw.get("stakes") or "").strip(),
        "themes": [str(item).strip() for item in (raw.get("themes") or []) if str(item).strip()],
        "notes": str(raw.get("notes") or "").strip(),
        "existing_entities": raw.get("existing_entities") if isinstance(raw.get("existing_entities"), dict) else {},
    }
    return normalized


def coerce_arcs(arcs: Any) -> list[dict[str, Any]]:
    """Coerce arcs."""
    if not isinstance(arcs, list):
        return []

    normalized: list[dict[str, Any]] = []
    for arc in arcs:
        # Process each arc from arcs.
        if not isinstance(arc, dict):
            continue
        name = str(arc.get("name") or "").strip()
        if not name:
            continue
        scenarios = arc.get("scenarios")
        if isinstance(scenarios, str):
            scenarios = [scenarios]
        if not isinstance(scenarios, list):
            scenarios = []
        normalized.append(
            {
                "name": name,
                "summary": str(arc.get("summary") or arc.get("description") or "").strip(),
                "objective": str(arc.get("objective") or "").strip(),
                "thread": str(arc.get("thread") or "").strip(),
                "status": str(arc.get("status") or "active").strip() or "active",
                "scenarios": list(dict.fromkeys(str(item).strip() for item in scenarios if str(item).strip())),
            }
        )
    return normalized


def coerce_generated_payload(payload: Any) -> dict[str, Any]:
    """Coerce generated payload."""
    parsed = deserialize_possible_json(payload)
    if not isinstance(parsed, dict):
        return {"arcs": []}

    arc_groups = parsed.get("arcs")
    if not isinstance(arc_groups, list):
        return {"arcs": []}

    normalized_groups: list[dict[str, Any]] = []
    for group in arc_groups:
        # Process each group from arc_groups.
        if not isinstance(group, dict):
            continue
        arc_name = str(group.get("arc_name") or "").strip()
        scenarios = group.get("scenarios")
        if not arc_name or not isinstance(scenarios, list):
            continue
        normalized_scenarios = [scenario for scenario in scenarios if isinstance(scenario, dict)]
        normalized_groups.append({"arc_name": arc_name, "scenarios": normalized_scenarios})

    return {"arcs": normalized_groups}
