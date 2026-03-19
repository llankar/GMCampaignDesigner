from __future__ import annotations

import json
from typing import Any

from modules.helpers.text_helpers import coerce_text
from .constraints import minimum_scenarios_per_arc


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
            "scenarios": ["Existing Scenario Title 1", "Existing Scenario Title 2", "Existing Scenario Title 3+"],
        }
    ],
}

ARC_SCENARIO_EXPANSION_SCHEMA = {
    "arcs": [
        {
            "arc_name": "string",
            "scenarios": [
                {
                    "Title": "string",
                    "Summary": "string",
                    "Secrets": "string",
                    "Places": ["Existing or new place names if needed"],
                    "NPCs": ["Existing or new NPC names if needed"],
                    "Objects": ["Existing or new object names if needed"],
                },
                {
                    "Title": "string",
                    "Summary": "string",
                    "Secrets": "string",
                    "Places": ["Existing or new place names if needed"],
                    "NPCs": ["Existing or new NPC names if needed"],
                    "Objects": ["Existing or new object names if needed"],
                },
            ],
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

    min_scenarios = minimum_scenarios_per_arc(len(scenario_catalog))

    return (
        "You are an expert tabletop RPG campaign architect.\n"
        "Return STRICT JSON only. No markdown, no explanations, no code fences.\n"
        "Design a globally coherent campaign progression using ONLY the existing scenarios provided.\n"
        f"Each arc must contain at least {min_scenarios} connected scenarios when enough scenarios exist in the catalog.\n"
        "Within each arc, order scenarios so they form a clear cause-and-effect chain: setup, escalation, then payoff or fallout.\n"
        "If an arc would otherwise be too short, merge it into a neighboring arc instead of creating an isolated one-scenario beat.\n"
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
        f"- Do not create arcs with fewer than {min_scenarios} scenarios unless the full scenario catalog itself contains fewer than that many scenarios.\n"
        "- Do not invent new scenario titles.\n"
    )


def build_arc_scenario_expansion_prompt(foundation: dict[str, Any], arcs: list[dict[str, Any]]) -> str:
    """Build the strict JSON prompt used to generate two new scenarios per arc."""

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
    arc_payload = [
        {
            "name": _clean(arc.get("name")),
            "summary": _clean(arc.get("summary") or arc.get("description")),
            "objective": _clean(arc.get("objective")),
            "thread": _clean(arc.get("thread")),
            "linked_scenarios": [_clean(title) for title in (arc.get("scenarios") or []) if _clean(title)],
        }
        for arc in arcs
        if _clean(arc.get("name"))
    ]

    return (
        "You are an expert tabletop RPG scenario writer.\n"
        "Return STRICT JSON only. No markdown, no explanations, no code fences.\n"
        "For EACH input arc, generate EXACTLY 2 brand-new scenarios that continue the parent arc's narrative thread.\n"
        "Each scenario payload must remain directly compatible with the existing scenario entity schema: Title, Summary, Secrets, Places, NPCs, Objects.\n"
        "Use the parent arc's name, summary, objective, thread, and linked scenario titles as the narrative seed.\n"
        "Preserve traceability inside the scenario text itself by explicitly mentioning the parent arc name, inherited thread, and the already-linked source scenario titles.\n"
        "Do not omit any arc. Do not generate more than 2 scenarios for any arc. Do not generate fewer than 2 scenarios for any arc.\n\n"
        "Campaign foundation:\n"
        f"{json.dumps(foundation_payload, ensure_ascii=False, indent=2)}\n\n"
        "Arc seeds:\n"
        f"{json.dumps(arc_payload, ensure_ascii=False, indent=2)}\n\n"
        "Required JSON schema:\n"
        f"{json.dumps(ARC_SCENARIO_EXPANSION_SCHEMA, ensure_ascii=False, indent=2)}\n\n"
        "Rules:\n"
        "- Make every generated Title unique within the full response.\n"
        "- Summary should read like a ready-to-run scenario hook and clearly continue the arc thread.\n"
        "- Secrets should include a short traceability block referencing the parent arc and source scenarios.\n"
        "- Places, NPCs, and Objects must always be JSON arrays, even when empty.\n"
        "- Keep each scenario self-contained enough to save directly as a scenario record.\n"
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
