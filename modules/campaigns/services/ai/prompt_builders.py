from __future__ import annotations

import json
from typing import Any

from modules.campaigns.services.ai.generation_policy import (
    build_hard_constraints_block,
    resolve_generation_defaults,
)
from modules.campaigns.services.generation_defaults_service import CampaignGenerationDefaultsService
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
                    "Scenes": [
                        {
                            "Title": "string",
                            "Objective": "string",
                            "Setup": "string",
                            "Challenge": "string",
                            "Stakes": "string",
                            "Twists": "string",
                            "GMNotes": "string",
                            "Outcome": "string",
                            "Entities": {
                                "NPCs": ["NPC names"],
                                "Creatures": ["Creature names"],
                                "Places": ["Place names"],
                                "Villains": ["Villain names"],
                                "Factions": ["Faction names"],
                                "Objects": ["Object names"],
                            },
                        },
                        {
                            "Title": "string",
                            "Objective": "string",
                            "Setup": "string",
                            "Challenge": "string",
                            "Stakes": "string",
                            "Twists": "string",
                            "GMNotes": "string",
                            "Outcome": "string",
                            "Entities": {
                                "NPCs": [],
                                "Creatures": [],
                                "Places": [],
                                "Villains": [],
                                "Factions": [],
                                "Objects": [],
                            },
                        },
                        {
                            "Title": "string",
                            "Objective": "string",
                            "Setup": "string",
                            "Challenge": "string",
                            "Stakes": "string",
                            "Twists": "string",
                            "GMNotes": "string",
                            "Outcome": "string",
                            "Entities": {
                                "NPCs": [],
                                "Creatures": [],
                                "Places": [],
                                "Villains": [],
                                "Factions": [],
                                "Objects": [],
                            },
                        },
                    ],
                    "Places": ["Existing or new place names if needed"],
                    "NPCs": ["Existing or new NPC names if needed"],
                    "Villains": ["At least 1 villain name"],
                    "Creatures": ["Existing or new creature names if needed"],
                    "Factions": ["At least 1 faction name"],
                    "Objects": ["Existing or new object names if needed"],
                    "EntityCreations": {
                        "villains": [
                            {
                                "Name": "string",
                                "Title": "string",
                                "Archetype": "string",
                                "ThreatLevel": "string",
                                "Description": "string",
                                "Scheme": "string",
                                "CurrentObjective": "string",
                                "Secrets": "string",
                                "Factions": ["Faction names"],
                                "Lieutenants": ["NPC names"],
                                "CreatureAgents": ["Creature names"],
                            }
                        ],
                        "factions": [
                            {
                                "Name": "string",
                                "Description": "string",
                                "Secrets": "string",
                                "Villains": ["Villain names"],
                            }
                        ],
                        "places": [
                            {
                                "Name": "string",
                                "Description": "string",
                                "Secrets": "string",
                                "NPCs": ["NPC names"],
                                "Villains": ["Villain names"],
                            }
                        ],
                        "npcs": [
                            {
                                "Name": "string",
                                "Role": "string",
                                "Description": "string",
                                "Secret": "string",
                                "Motivation": "string",
                                "Background": "string",
                                "Personality": "string",
                                "Factions": ["Faction names"],
                            }
                        ],
                        "creatures": [
                            {
                                "Name": "string",
                                "Type": "string",
                                "Description": "string",
                                "Weakness": "string",
                                "Powers": "string",
                            }
                        ],
                    },
                },
                {
                    "Title": "string",
                    "Summary": "string",
                    "Secrets": "string",
                    "Scenes": [
                        {
                            "Title": "string",
                            "Objective": "string",
                            "Setup": "string",
                            "Challenge": "string",
                            "Stakes": "string",
                            "Twists": "string",
                            "GMNotes": "string",
                            "Outcome": "string",
                            "Entities": {
                                "NPCs": ["NPC names"],
                                "Creatures": ["Creature names"],
                                "Places": ["Place names"],
                                "Villains": ["Villain names"],
                                "Factions": ["Faction names"],
                                "Objects": ["Object names"],
                            },
                        }
                    ],
                    "Places": ["Existing or new place names if needed"],
                    "NPCs": ["Existing or new NPC names if needed"],
                    "Villains": ["At least 1 villain name"],
                    "Creatures": ["Existing or new creature names if needed"],
                    "Factions": ["At least 1 faction name"],
                    "Objects": ["Existing or new object names if needed"],
                    "EntityCreations": {
                        "villains": [],
                        "factions": [],
                        "places": [],
                        "npcs": [],
                        "creatures": [],
                    },
                },
            ],
        }
    ],
}


def build_arc_generation_prompt(
    foundation: dict[str, Any],
    scenarios: list[dict[str, Any]],
    *,
    generation_defaults_service: CampaignGenerationDefaultsService | None = None,
) -> str:
    """Build the strict JSON prompt used to generate campaign arcs from scenarios."""
    generation_defaults = resolve_generation_defaults(
        foundation,
        generation_defaults_service=generation_defaults_service,
    )

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
        "existing_entities": {
            entity_type: [_clean(name) for name in (foundation.get("existing_entities", {}).get(entity_type) or []) if _clean(name)]
            for entity_type in ("villains", "factions", "places", "npcs", "creatures")
        },
        "generation_defaults": {
            "main_pc_factions": [_clean(name) for name in (generation_defaults.get("main_pc_factions") or []) if _clean(name)],
            "protected_factions": [_clean(name) for name in (generation_defaults.get("protected_factions") or []) if _clean(name)],
            "forbidden_antagonist_factions": [
                _clean(name)
                for name in (generation_defaults.get("forbidden_antagonist_factions") or [])
                if _clean(name)
            ],
            "allow_optional_conflicts": bool(generation_defaults.get("allow_optional_conflicts", True)),
        },
    }
    hard_constraints_block = build_hard_constraints_block(generation_defaults)

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
        f"{_format_prompt_block(hard_constraints_block)}"
        "- The thread field on each arc must match one of the generated thread names.\n"
        "- Prefer broad campaign continuity over isolated arc ideas.\n"
        f"- Do not create arcs with fewer than {min_scenarios} scenarios unless the full scenario catalog itself contains fewer than that many scenarios.\n"
        "- Do not invent new scenario titles.\n"
    )


def build_arc_scenario_expansion_prompt(
    foundation: dict[str, Any],
    arcs: list[dict[str, Any]],
    *,
    existing_scenarios: list[dict[str, Any]] | None = None,
    generation_defaults_service: CampaignGenerationDefaultsService | None = None,
) -> str:
    """Build the strict JSON prompt used to generate two new scenarios per arc."""
    generation_defaults = resolve_generation_defaults(
        foundation,
        generation_defaults_service=generation_defaults_service,
    )

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
        "existing_entities": {
            entity_type: [
                _clean(name)
                for name in (foundation.get("existing_entities", {}).get(entity_type) or [])
                if _clean(name)
            ]
            for entity_type in ("villains", "factions", "places", "npcs", "creatures")
        },
        "generation_defaults": {
            "main_pc_factions": [
                _clean(name)
                for name in (generation_defaults.get("main_pc_factions") or [])
                if _clean(name)
            ],
            "protected_factions": [
                _clean(name)
                for name in (generation_defaults.get("protected_factions") or [])
                if _clean(name)
            ],
            "forbidden_antagonist_factions": [
                _clean(name)
                for name in (generation_defaults.get("forbidden_antagonist_factions") or [])
                if _clean(name)
            ],
            "allow_optional_conflicts": bool(generation_defaults.get("allow_optional_conflicts", True)),
        },
    }
    hard_constraints_block = build_hard_constraints_block(generation_defaults)
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
    existing_scenario_payload = [
        {
            "title": _scenario_title(scenario),
            "summary": _scenario_summary(scenario),
            "scenes": _scenario_scene_titles(scenario),
        }
        for scenario in (existing_scenarios or [])
        if _scenario_title(scenario)
    ]

    return (
        "You are an expert tabletop RPG scenario writer.\n"
        "Return STRICT JSON only. No markdown, no explanations, no code fences.\n"
        "For EACH input arc, generate EXACTLY 2 brand-new scenarios that continue the parent arc's narrative thread.\n"
        "Each scenario payload must remain directly compatible with the existing scenario entity schema and be ready to save immediately.\n"
        "Use the parent arc's name, summary, objective, thread, and linked scenario titles as the narrative seed.\n"
        "Preserve traceability inside the scenario text itself by explicitly mentioning the parent arc name, inherited thread, and the already-linked source scenario titles.\n"
        "Prefer reusing existing entities from the campaign catalog in about 90% of links. Only invent a new villain, faction, place, NPC, or creature when the arc genuinely needs one.\n"
        "If you invent a new linked entity that is not listed in campaign foundation.existing_entities, add its full record under EntityCreations in the same scenario payload.\n"
        "Do not omit any arc. Do not generate more than 2 scenarios for any arc. Do not generate fewer than 2 scenarios for any arc.\n\n"
        "Campaign foundation:\n"
        f"{json.dumps(foundation_payload, ensure_ascii=False, indent=2)}\n\n"
        "Arc seeds:\n"
        f"{json.dumps(arc_payload, ensure_ascii=False, indent=2)}\n\n"
        "Existing scenario and scene catalog (parse these before generating anything new):\n"
        f"{json.dumps(existing_scenario_payload, ensure_ascii=False, indent=2)}\n\n"
        "Required JSON schema:\n"
        f"{json.dumps(ARC_SCENARIO_EXPANSION_SCHEMA, ensure_ascii=False, indent=2)}\n\n"
        "Rules:\n"
        "- Make every generated Title unique within the full response.\n"
        "- Summary should read like a ready-to-run scenario hook and clearly continue the arc thread.\n"
        "- Secrets should include a short traceability block referencing the parent arc and source scenarios.\n"
        "- Scenes must always be a JSON array with at least 3 playable scene objects.\n"
        "- Every scene must include concrete GM-facing details (setup, challenge, stakes, twists, and outcome), not vague summaries.\n"
        "- Scene Entities lists must reference campaign foundation.existing_entities or matching EntityCreations records.\n"
        "- Each scenario must include at least 1 villain, at least 1 faction, and at least 1 place.\n"
        "- NPCs and Creatures are optional, but include them whenever the premise naturally needs them.\n"
        "- Places, NPCs, Villains, Creatures, Factions, and Objects must always be JSON arrays, even when empty.\n"
        "- Reuse names from campaign foundation.existing_entities whenever they fit.\n"
        "- If you use any villain, faction, place, NPC, or creature name that is not in campaign foundation.existing_entities, include it in EntityCreations with a matching Name.\n"
        "- Keep each scenario self-contained enough to save directly as a scenario record.\n"
        f"{_format_prompt_block(hard_constraints_block)}"
    )


def _format_prompt_block(block: str) -> str:
    if not block:
        return ""
    return f"{block}\n"


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


def _scenario_scene_titles(scenario: dict[str, Any]) -> list[str]:
    scenes = scenario.get("Scenes")
    if not isinstance(scenes, list):
        return []
    titles: list[str] = []
    for scene in scenes:
        if isinstance(scene, dict):
            title = _clean(scene.get("Title"))
        else:
            title = _clean(scene)
        if title:
            titles.append(title)
    return titles


def _clean(value: Any) -> str:
    return coerce_text(value).strip()
