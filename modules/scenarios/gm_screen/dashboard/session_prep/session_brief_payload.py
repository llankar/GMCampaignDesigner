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
    arc_details: list[str]
    dashboard_fields: list[str]
    gm_priority_notes: list[str]


def build_session_brief_payload(
    *, fields: list[dict[str, Any]], campaign_item: dict[str, Any] | None
) -> SessionBriefPayload:
    summary = _extract_summary(fields)
    active_arcs = _extract_active_arcs(fields)
    arc_details = _extract_arc_details(fields)
    dashboard_fields = _extract_dashboard_fields(fields)
    gm_priority_notes = build_session_prep_summary(fields).critical_reminders
    return SessionBriefPayload(
        summary=summary,
        active_arcs=active_arcs,
        arc_details=arc_details,
        dashboard_fields=dashboard_fields,
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
            arc_name = str(arc.get("name") or "").strip() or "Unnamed arc"
            objective = str(arc.get("objective") or "").strip()
            lines.append(f"{arc_name} — {objective}" if objective else arc_name)
        return lines
    return []


def _extract_arc_details(fields: list[dict[str, Any]]) -> list[str]:
    for field in fields:
        if str(field.get("name") or "").strip().lower() != "arcs":
            continue

        details: list[str] = []
        for index, arc in enumerate(coerce_arc_list(field.get("value")), start=1):
            name = str(arc.get("name") or "").strip() or f"Arc #{index}"
            segments = [f"Arc {index}: {name}"]
            for key, raw_value in arc.items():
                if str(key).strip().lower() == "name":
                    continue
                rendered = _render_arc_value(raw_value)
                if not rendered:
                    continue
                segments.append(f"{key}: {rendered}")

            details.append(" | ".join(segments))
        return details
    return []


def _extract_dashboard_fields(fields: list[dict[str, Any]]) -> list[str]:
    lines: list[str] = []
    for field in fields:
        name = str(field.get("name") or "").strip()
        if not name:
            continue

        values = _extract_text_values(field)
        if not values:
            continue

        lines.append(f"{name}: {' | '.join(values)}")
    return lines


def _extract_text_values(field: dict[str, Any]) -> list[str]:
    if field.get("type") == "list":
        return [str(value).strip() for value in (field.get("values") or []) if str(value).strip()]

    value = field.get("value")
    if isinstance(value, list):
        rendered_items: list[str] = []
        for item in value:
            rendered = _render_arc_value(item)
            if rendered:
                rendered_items.append(rendered)
        return rendered_items

    text = str(value or "").strip()
    return [text] if text else []


def _render_arc_value(raw_value: Any) -> str:
    if isinstance(raw_value, list):
        rendered = [str(item).strip() for item in raw_value if str(item).strip()]
        return ", ".join(rendered)
    return str(raw_value or "").strip()
