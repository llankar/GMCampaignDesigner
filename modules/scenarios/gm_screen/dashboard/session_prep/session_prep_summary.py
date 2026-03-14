from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from modules.campaigns.shared.arc_parser import coerce_arc_list

_OBJECTIVE_KEYWORDS = ("objective", "goal", "mission", "quest", "priorit")
_NPC_KEYWORDS = ("npc", "pnj", "character", "ally", "villain")
_PLACE_KEYWORDS = ("place", "location", "lieu", "site", "region")
_CRITICAL_KEYWORDS = ("critical", "urgent", "key", "important", "priorit")


@dataclass(frozen=True)
class SessionPrepSummary:
    active_objectives: list[str]
    in_progress_arcs: list[str]
    critical_reminders: list[str]


def build_session_prep_summary(fields: Iterable[dict[str, Any]]) -> SessionPrepSummary:
    normalized_fields = list(fields)
    active_objectives = _collect_active_objectives(normalized_fields)
    in_progress_arcs = _collect_in_progress_arcs(normalized_fields)
    critical_reminders = _collect_critical_reminders(normalized_fields)

    return SessionPrepSummary(
        active_objectives=active_objectives,
        in_progress_arcs=in_progress_arcs,
        critical_reminders=critical_reminders,
    )


def _collect_active_objectives(fields: list[dict[str, Any]]) -> list[str]:
    objectives: list[str] = []
    for field in fields:
        name = str(field.get("name") or "")
        lowered = name.lower()
        if not any(keyword in lowered for keyword in _OBJECTIVE_KEYWORDS):
            continue
        values = _extract_text_values(field)
        objectives.extend(values)

    return _dedupe_preserve_order(objectives)


def _collect_in_progress_arcs(fields: list[dict[str, Any]]) -> list[str]:
    for field in fields:
        if str(field.get("name") or "").strip().lower() != "arcs":
            continue

        lines: list[str] = []
        for arc in coerce_arc_list(field.get("value")):
            status = str(arc.get("status") or "").strip().lower()
            if status != "in progress":
                continue
            arc_name = str(arc.get("name") or "").strip() or "Arc sans nom"
            objective = str(arc.get("objective") or "").strip()
            if objective:
                lines.append(f"{arc_name} — {objective}")
            else:
                lines.append(arc_name)

        return _dedupe_preserve_order(lines)

    return []


def _collect_critical_reminders(fields: list[dict[str, Any]]) -> list[str]:
    reminders: list[str] = []
    for field in fields:
        name = str(field.get("name") or "")
        lowered = name.lower()
        mentions_actor_or_place = any(key in lowered for key in _NPC_KEYWORDS + _PLACE_KEYWORDS)
        mentions_priority = any(key in lowered for key in _CRITICAL_KEYWORDS)

        if not (mentions_actor_or_place or mentions_priority):
            continue

        values = _extract_text_values(field)
        if not values:
            continue

        if mentions_priority:
            reminders.extend(values)
            continue

        label = "PNJ" if any(key in lowered for key in _NPC_KEYWORDS) else "Lieux"
        reminders.extend([f"{label}: {value}" for value in values])

    return _dedupe_preserve_order(reminders)


def _extract_text_values(field: dict[str, Any]) -> list[str]:
    if field.get("type") == "list":
        raw_values = field.get("values") or []
        return [str(value).strip() for value in raw_values if str(value).strip()]

    value = str(field.get("value") or "").strip()
    if not value:
        return []

    return [segment.strip(" -•\t") for segment in value.splitlines() if segment.strip()]


def _dedupe_preserve_order(values: Iterable[str]) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()

    for value in values:
        key = value.strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        ordered.append(value.strip())

    return ordered
