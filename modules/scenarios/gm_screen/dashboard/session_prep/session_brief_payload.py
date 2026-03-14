from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from modules.campaigns.shared.arc_parser import coerce_arc_list

from modules.scenarios.gm_screen.dashboard.session_prep.session_prep_summary import (
    build_session_prep_summary,
)

_SUMMARY_KEYS = ("summary", "résumé", "resume", "synopsis", "pitch", "overview", "description")


@dataclass(frozen=True)
class SessionBriefPayload:
    summary: str
    active_arcs: list[str]
    linked_scenarios: list[str]
    gm_priority_notes: list[str]


def build_session_brief_payload(
    *, fields: list[dict[str, Any]], campaign_item: dict[str, Any] | None
) -> SessionBriefPayload:
    summary = _extract_summary(fields)
    active_arcs = _extract_active_arcs(fields)
    linked_scenarios = _extract_linked_scenarios(campaign_item)
    gm_priority_notes = build_session_prep_summary(fields).critical_reminders
    return SessionBriefPayload(
        summary=summary,
        active_arcs=active_arcs,
        linked_scenarios=linked_scenarios,
        gm_priority_notes=gm_priority_notes,
    )


def _extract_summary(fields: list[dict[str, Any]]) -> str:
    for field in fields:
        name = str(field.get("name") or "").strip().lower()
        if not any(token in name for token in _SUMMARY_KEYS):
            continue
        value = str(field.get("value") or "").strip()
        if value:
            return value

    for field in fields:
        value = str(field.get("value") or "").strip()
        if value:
            return value
    return ""


def _extract_active_arcs(fields: list[dict[str, Any]]) -> list[str]:
    for field in fields:
        if str(field.get("name") or "").strip().lower() != "arcs":
            continue

        lines: list[str] = []
        for arc in coerce_arc_list(field.get("value")):
            status = str(arc.get("status") or "").strip().lower()
            if status not in {"in progress", "active", "ongoing"}:
                continue
            arc_name = str(arc.get("name") or "").strip() or "Arc sans nom"
            objective = str(arc.get("objective") or "").strip()
            lines.append(f"{arc_name} — {objective}" if objective else arc_name)
        return lines
    return []


def _extract_linked_scenarios(campaign_item: dict[str, Any] | None) -> list[str]:
    if not campaign_item:
        return []
    scenarios = campaign_item.get("LinkedScenarios") or []
    if not isinstance(scenarios, list):
        return []
    seen: set[str] = set()
    ordered: list[str] = []
    for scenario in scenarios:
        label = str(scenario).strip()
        key = label.lower()
        if not label or key in seen:
            continue
        seen.add(key)
        ordered.append(label)
    return ordered
