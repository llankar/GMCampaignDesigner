from __future__ import annotations

import json
from typing import Any

from modules.helpers.text_helpers import coerce_text


ARC_GENERATION_SCHEMA = {
    "campaign": {
        "name": "string",
        "summary": "string",
        "objective": "string",
        "coherence_notes": "string",
    },
    "threads": [
        {
            "name": "string",
            "summary": "string",
            "arcs": ["Arc name"],
        }
    ],
    "arcs": [
        {
            "name": "string",
            "summary": "string",
            "objective": "string",
            "status": "Planned|In Progress|Completed|Paused",
            "thread": "string",
            "scenarios": ["Existing Scenario Title, max 3 items"],
        }
    ],
}


def build_arc_generation_prompt(foundation: dict[str, Any], scenarios: list[dict[str, Any]]) -> str:
    """Build the strict JSON prompt used to generate campaign arcs from scenarios."""

    scenario_catalog = [
        {
            "title": _scenario_title(scenario),
            "summary": _scenario_summary(scenario),
            "details": _scenario_details(scenario),
        }
        for scenario in scenarios
        if _scenario_title(scenario)
    ]

    foundation_payload = {
        "name": _clean(foundation.get("name")),
        "genre": _clean(foundation.get("genre")),
        "tone": _clean(foundation.get("tone")),
        "status": _clean(foundation.get("status")),
        "logline": _clean(foundation.get("logline")),
        "setting": _clean(foundation.get("setting")),
        "main_objective": _clean(foundation.get("main_objective")),
        "stakes": _clean(foundation.get("stakes")),
        "themes": [_clean(theme) for theme in (foundation.get("themes") or []) if _clean(theme)],
        "notes": _clean(foundation.get("notes")),
    }

    return (
        "You are an expert tabletop RPG campaign architect.\n"
        "Return STRICT JSON only. No markdown, no explanations, no code fences.\n"
        "Design a globally coherent campaign progression using ONLY the existing scenarios provided.\n"
        "You may leave an arc with fewer than 3 scenarios, but never include more than 3 scenarios in one arc.\n"
        "Every scenario reference must match an existing scenario title exactly.\n"
        "Create one or more campaign threads that span multiple arcs when appropriate.\n"
        "Order arcs for progression from early to late campaign.\n\n"
        "Campaign foundation:\n"
        f"{json.dumps(foundation_payload, ensure_ascii=False, indent=2)}\n\n"
        "Scenario catalog (full records already loaded from the wrapper; summaries below are derived from those records):\n"
        f"{json.dumps(scenario_catalog, ensure_ascii=False, indent=2)}\n\n"
        "Required JSON schema:\n"
        f"{json.dumps(ARC_GENERATION_SCHEMA, ensure_ascii=False, indent=2)}\n\n"
        "Rules:\n"
        "- Use concise but actionable summaries and objectives.\n"
        "- Keep status realistic for a planning workflow; default to Planned unless campaign state strongly implies otherwise.\n"
        "- The thread field on each arc must match one of the generated thread names.\n"
        "- Prefer broad campaign continuity over isolated arc ideas.\n"
        "- Do not invent new scenario titles.\n"
    )


def _scenario_title(scenario: dict[str, Any]) -> str:
    return _clean(scenario.get("Title") or scenario.get("Name"))


def _scenario_summary(scenario: dict[str, Any]) -> str:
    return _clean(scenario.get("Summary") or scenario.get("Description") or scenario.get("Logline"))


def _scenario_details(scenario: dict[str, Any]) -> dict[str, Any]:
    details: dict[str, Any] = {}
    for key in ("Secrets", "Scenes", "NPCs", "Places", "Factions", "LinkedNPCs", "LinkedPlaces"):
        value = scenario.get(key)
        if value in (None, "", []):
            continue
        if isinstance(value, list):
            normalized = [_clean(item) for item in value if _clean(item)]
            if normalized:
                details[key] = normalized
            continue
        text_value = _clean(value)
        if text_value:
            details[key] = text_value
    return details


def _clean(value: Any) -> str:
    return coerce_text(value).strip()
