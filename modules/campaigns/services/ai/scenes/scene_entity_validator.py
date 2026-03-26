from __future__ import annotations

import difflib
import json
from typing import Any

from modules.campaigns.services.ai.arc_scenario_entities import ENTITY_WRAPPER_SPECS


SCENE_ENTITY_TYPES = tuple(ENTITY_WRAPPER_SPECS.keys())


class SceneEntityValidationError(ValueError):
    """Raised when scene entity references cannot be normalized."""


def validate_and_fix_scene_entity_links(
    *,
    title: str,
    ai_client: Any,
    links: dict[str, list[str]],
    scene_entities: dict[str, list[str]],
    entity_creations: dict[str, list[dict[str, Any]]],
    existing_entities: dict[str, set[str]] | None,
) -> tuple[dict[str, list[str]], dict[str, list[str]], dict[str, list[dict[str, Any]]]]:
    """Resolve unknown scene references against DB entities, with AI-assisted repair fallback."""

    if existing_entities is None:
        return links, scene_entities, entity_creations

    fixed_links = {entity_type: list(links.get(entity_type) or []) for entity_type in SCENE_ENTITY_TYPES}
    fixed_scene_entities = {
        entity_type: list(scene_entities.get(entity_type) or [])
        for entity_type in SCENE_ENTITY_TYPES
    }

    unknown_by_type = _collect_unknown_entities(
        links=fixed_links,
        scene_entities=fixed_scene_entities,
        entity_creations=entity_creations,
        existing_entities=existing_entities,
    )
    if not any(unknown_by_type.values()):
        return fixed_links, fixed_scene_entities, entity_creations

    deterministic_mapping = _resolve_with_similarity(unknown_by_type, existing_entities)
    _apply_rename_mapping(fixed_links, fixed_scene_entities, deterministic_mapping)

    remaining_unknown = _collect_unknown_entities(
        links=fixed_links,
        scene_entities=fixed_scene_entities,
        entity_creations=entity_creations,
        existing_entities=existing_entities,
    )
    if not any(remaining_unknown.values()):
        return fixed_links, fixed_scene_entities, entity_creations

    ai_mapping = _resolve_with_ai(
        title=title,
        ai_client=ai_client,
        unknown_by_type=remaining_unknown,
        existing_entities=existing_entities,
    )
    _apply_rename_mapping(fixed_links, fixed_scene_entities, ai_mapping)

    final_unknown = _collect_unknown_entities(
        links=fixed_links,
        scene_entities=fixed_scene_entities,
        entity_creations=entity_creations,
        existing_entities=existing_entities,
    )

    if any(final_unknown.values()):
        entity_creations = _append_placeholders_for_unknown(
            entity_creations=entity_creations,
            unknown_by_type=final_unknown,
            title=title,
        )
        # Make sure scenario-level links include newly auto-created entities.
        for entity_type, names in final_unknown.items():
            if not names:
                continue
            _extend_unique(fixed_links[entity_type], names)
            _extend_unique(fixed_scene_entities[entity_type], names)

    return fixed_links, fixed_scene_entities, entity_creations


def _collect_unknown_entities(
    *,
    links: dict[str, list[str]],
    scene_entities: dict[str, list[str]],
    entity_creations: dict[str, list[dict[str, Any]]],
    existing_entities: dict[str, set[str]],
) -> dict[str, list[str]]:
    unknown: dict[str, list[str]] = {entity_type: [] for entity_type in SCENE_ENTITY_TYPES}

    for entity_type in SCENE_ENTITY_TYPES:
        known_existing = existing_entities.get(entity_type, set())
        known_created = {
            str(item.get("Name") or "").strip().casefold()
            for item in (entity_creations.get(entity_type) or [])
            if str(item.get("Name") or "").strip()
        }

        merged_values = list(links.get(entity_type) or []) + list(scene_entities.get(entity_type) or [])
        for value in merged_values:
            cleaned = str(value or "").strip()
            if not cleaned:
                continue
            key = cleaned.casefold()
            if key in known_existing or key in known_created:
                continue
            if key in {item.casefold() for item in unknown[entity_type]}:
                continue
            unknown[entity_type].append(cleaned)

    return unknown


def _resolve_with_similarity(
    unknown_by_type: dict[str, list[str]],
    existing_entities: dict[str, set[str]],
) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for entity_type, unknown_values in unknown_by_type.items():
        existing_names = sorted(existing_entities.get(entity_type) or set())
        if not existing_names:
            continue
        for value in unknown_values:
            match = difflib.get_close_matches(value.casefold(), existing_names, n=1, cutoff=0.88)
            if not match:
                continue
            mapping[value] = _restore_original_case(match[0], existing_names)
    return mapping


def _resolve_with_ai(
    *,
    title: str,
    ai_client: Any,
    unknown_by_type: dict[str, list[str]],
    existing_entities: dict[str, set[str]],
) -> dict[str, str]:
    if ai_client is None:
        return {}

    payload = {
        "scenario_title": title,
        "unknown_references": unknown_by_type,
        "available_database_entities": {
            entity_type: sorted(existing_entities.get(entity_type) or set())
            for entity_type in SCENE_ENTITY_TYPES
        },
        "rules": [
            "Return strict JSON only.",
            "Use key 'resolved' with object values grouped by entity type.",
            "Each entry must include 'source' and 'target'.",
            "Use an empty array for entity types with no mapping.",
            "Only map to names present in available_database_entities.",
        ],
        "schema": {
            "resolved": {
                entity_type: [{"source": "string", "target": "string"}]
                for entity_type in SCENE_ENTITY_TYPES
            }
        },
    }
    messages = [
        {"role": "system", "content": "Resolve misspelled RPG entity references using provided database catalogs."},
        {
            "role": "user",
            "content": (
                "Fix unknown scene entity references by mapping each source name to the closest valid database name. "
                "If no safe mapping exists, omit that source from resolved entries.\n"
                + json.dumps(payload, ensure_ascii=False, indent=2)
            ),
        },
    ]

    try:
        raw_response = ai_client.chat(messages)
        parsed = _parse_json_object(raw_response)
    except Exception:
        return {}

    resolved = parsed.get("resolved") if isinstance(parsed, dict) else None
    if not isinstance(resolved, dict):
        return {}

    mapping: dict[str, str] = {}
    for entity_type in SCENE_ENTITY_TYPES:
        entries = resolved.get(entity_type)
        if not isinstance(entries, list):
            continue
        allowed = existing_entities.get(entity_type) or set()
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            source = str(entry.get("source") or "").strip()
            target = str(entry.get("target") or "").strip()
            if not source or not target:
                continue
            if target.casefold() not in allowed:
                continue
            mapping[source] = target

    return mapping


def _parse_json_object(raw: Any) -> dict[str, Any]:
    text = str(raw or "").strip()
    if not text:
        raise SceneEntityValidationError("AI returned empty scene entity resolution response")

    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        pass

    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end < 0 or end <= start:
        raise SceneEntityValidationError("AI returned invalid JSON for scene entity resolution")

    parsed = json.loads(text[start : end + 1])
    return parsed if isinstance(parsed, dict) else {}


def _append_placeholders_for_unknown(
    *,
    entity_creations: dict[str, list[dict[str, Any]]],
    unknown_by_type: dict[str, list[str]],
    title: str,
) -> dict[str, list[dict[str, Any]]]:
    created = {entity_type: list(entity_creations.get(entity_type) or []) for entity_type in SCENE_ENTITY_TYPES}

    for entity_type, names in unknown_by_type.items():
        if not names:
            continue
        existing = {
            str(item.get("Name") or "").strip().casefold()
            for item in created[entity_type]
            if str(item.get("Name") or "").strip()
        }
        for name in names:
            key = name.casefold()
            if key in existing:
                continue
            created[entity_type].append(_build_placeholder(entity_type, name, title))
            existing.add(key)

    return created


def _build_placeholder(entity_type: str, name: str, title: str) -> dict[str, Any]:
    note = f"Auto-created by Scene Validator from scenario '{title}'."
    if entity_type == "villains":
        return {
            "Name": name,
            "Title": "",
            "Archetype": "",
            "ThreatLevel": "",
            "Description": note,
            "Scheme": note,
            "CurrentObjective": "",
            "Secrets": "",
            "Factions": [],
            "Lieutenants": [],
            "CreatureAgents": [],
        }
    if entity_type == "factions":
        return {"Name": name, "Description": note, "Secrets": "", "Villains": []}
    if entity_type == "places":
        return {"Name": name, "Description": note, "Secrets": "", "NPCs": [], "Villains": []}
    if entity_type == "npcs":
        return {
            "Name": name,
            "Role": "",
            "Description": note,
            "Secret": "",
            "Motivation": "",
            "Background": note,
            "Personality": "",
            "Factions": [],
        }
    if entity_type == "creatures":
        return {"Name": name, "Type": "", "Description": note, "Weakness": "", "Powers": ""}
    return {"Name": name}


def _apply_rename_mapping(
    links: dict[str, list[str]],
    scene_entities: dict[str, list[str]],
    mapping: dict[str, str],
) -> None:
    if not mapping:
        return

    for entity_type in SCENE_ENTITY_TYPES:
        links[entity_type] = _replace_values(links.get(entity_type) or [], mapping)
        scene_entities[entity_type] = _replace_values(scene_entities.get(entity_type) or [], mapping)


def _replace_values(values: list[str], mapping: dict[str, str]) -> list[str]:
    replaced: list[str] = []
    for value in values:
        target = mapping.get(value, value)
        if target.casefold() in {existing.casefold() for existing in replaced}:
            continue
        replaced.append(target)
    return replaced


def _restore_original_case(target: str, existing_values: list[str]) -> str:
    for value in existing_values:
        if value.casefold() == target.casefold():
            return value
    return target


def _extend_unique(target: list[str], values: list[str]) -> None:
    seen = {name.casefold() for name in target}
    for value in values:
        if value.casefold() in seen:
            continue
        target.append(value)
        seen.add(value.casefold())
