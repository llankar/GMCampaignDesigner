"""Payload helpers for generic scene indicator."""
from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from modules.helpers.text_helpers import deserialize_possible_json
from modules.scenarios.scene_structured_fields import (
    get_structured_field_name_for_section_key,
    migrate_scene_to_structured_fields,
    parse_scene_sections_with_structured_fallback,
)


_NAME_FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "NPCs": ("NPCs", "npcs", "InvolvedNPCs", "Participants", "Allies", "Characters"),
    "Places": ("Places", "places", "ImportantLocations", "Locations"),
    "Maps": ("Maps", "maps", "Handouts"),
    "Villains": ("Villains", "villains"),
    "Creatures": ("Creatures", "creatures"),
}

_LINK_FIELD_ALIASES: tuple[str, ...] = (
    "Links",
    "links",
    "LinkData",
    "linkData",
    "NextScenes",
    "nextScenes",
)


def _flatten_strings(value: Any) -> list[str]:
    """Internal helper for flatten strings."""
    parsed = deserialize_possible_json(value)
    if isinstance(parsed, dict):
        # Handle the branch where isinstance(parsed, dict).
        values: list[str] = []
        for item in parsed.values():
            values.extend(_flatten_strings(item))
        return values
    if isinstance(parsed, (list, tuple, set)):
        # Handle the branch where isinstance(parsed, (list, tuple, set)).
        values: list[str] = []
        for item in parsed:
            values.extend(_flatten_strings(item))
        return values
    if parsed is None:
        return []
    text = str(parsed).strip()
    return [text] if text else []


def _normalize_names(values: Iterable[str]) -> list[str]:
    """Normalize names."""
    normalized: list[str] = []
    seen: set[str] = set()
    for raw in values:
        # Process each raw from values.
        parts = [part.strip() for part in str(raw).split(",") if part.strip()]
        candidates = parts or [str(raw).strip()]
        for candidate in candidates:
            # Process each candidate from candidates.
            lowered = candidate.lower()
            if not candidate or lowered in seen:
                continue
            seen.add(lowered)
            normalized.append(candidate)
    return normalized


def _collect_names(scene_dict: dict[str, Any], field_name: str) -> list[str]:
    """Collect names."""
    aliases = _NAME_FIELD_ALIASES.get(field_name, (field_name,))
    merged: list[str] = []
    for alias in aliases:
        merged.extend(_flatten_strings(scene_dict.get(alias)))
    return _normalize_names(merged)


def _coerce_links(value: Any) -> list[dict[str, Any]]:
    """Coerce links."""
    links: list[dict[str, Any]] = []
    if value is None:
        return links

    parsed = deserialize_possible_json(value)
    if isinstance(parsed, list):
        # Handle the branch where isinstance(parsed, list).
        for item in parsed:
            links.extend(_coerce_links(item))
        return links

    if isinstance(parsed, dict):
        # Handle the branch where isinstance(parsed, dict).
        payload = {k: deserialize_possible_json(v) for k, v in parsed.items()}
        target = None
        text = None

        for key in ("Target", "target", "Scene", "scene", "Next", "next", "Id", "id", "Reference", "reference"):
            if key in payload:
                target = payload[key]
                break
        for key in ("Text", "text", "Label", "label", "Description", "description", "Choice", "choice"):
            if key in payload:
                text = payload[key]
                break

        target_texts = _flatten_strings(target)
        text_texts = _flatten_strings(text)
        if target_texts:
            target_value: Any = target_texts[0]
        elif isinstance(target, (int, float)):
            target_value = int(target)
        else:
            target_value = None

        if text_texts:
            text_value = text_texts[0]
        elif isinstance(text, (int, float)):
            text_value = str(text)
        else:
            text_value = ""

        if target_value is not None:
            links.append({"target": target_value, "text": text_value or str(target_value)})
        return links

    if isinstance(parsed, (int, float)):
        links.append({"target": int(parsed), "text": str(int(parsed))})
        return links

    text_value = str(parsed).strip()
    if text_value:
        links.append({"target": text_value, "text": text_value})
    return links


def _merge_links(scene_dict: dict[str, Any]) -> list[dict[str, Any]]:
    """Merge links."""
    merged: list[dict[str, Any]] = []
    for alias in _LINK_FIELD_ALIASES:
        merged.extend(_coerce_links(scene_dict.get(alias)))

    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for link in merged:
        # Process each link from merged.
        target = str(link.get("target") or "").strip()
        if not target:
            continue
        text = str(link.get("text") or target).strip() or target
        key = (target.lower(), text.lower())
        if key in seen:
            continue
        seen.add(key)
        deduped.append({"target": target, "text": text})
    return deduped


def _collect_names_from_sections(body_text: str, section_key: str) -> list[str]:
    """Collect names from sections."""
    parsed = parse_scene_sections_with_structured_fallback({}, body_text)
    sections = parsed.get("sections") or []
    collected: list[str] = []
    for section in sections:
        # Process each section from sections.
        if str(section.get("key") or "").lower() != section_key:
            continue
        items = section.get("items") or []
        collected.extend(_normalize_names([str(item) for item in items]))
    return collected


def migrate_scene_indicator_scene(scene_dict: dict[str, Any], body_text: str) -> dict[str, Any]:
    """Populate scene payload with canonical structured section fields."""
    return migrate_scene_to_structured_fields(scene_dict, body_text)


def build_scene_indicator_payload(scene_dict: dict[str, Any], body_text: str) -> dict[str, Any]:
    """Build scene indicator payload."""
    scene_dict = migrate_scene_indicator_scene(scene_dict, body_text)
    npcs = _collect_names(scene_dict, "NPCs")
    places = _collect_names(scene_dict, "Places")
    maps = _collect_names(scene_dict, "Maps")
    villains = _collect_names(scene_dict, "Villains")
    creatures = _collect_names(scene_dict, "Creatures")

    if not npcs:
        npcs = _normalize_names(scene_dict.get("SceneNPCs") or [])
    if not places:
        places = _normalize_names(scene_dict.get("SceneLocations") or [])
    if not npcs:
        npcs = _collect_names_from_sections(body_text, "involved npcs")
    if not places:
        places = _collect_names_from_sections(body_text, "important locations")

    sections_payload = parse_scene_sections_with_structured_fallback(scene_dict, body_text)
    section_field_values: dict[str, list[str]] = {}
    for section in sections_payload.get("sections") or []:
        section_key = str(section.get("key") or "").lower()
        field_name = get_structured_field_name_for_section_key(section_key)
        if not field_name:
            continue
        section_field_values[field_name] = _normalize_names(section.get("items") or [])

    links = _merge_links(scene_dict)

    return {
        "npc_names": npcs,
        "place_names": places,
        "map_names": maps,
        "villain_names": villains,
        "creature_names": creatures,
        "links": links,
        "structured_sections": {
            field_name: section_field_values.get(field_name, _normalize_names(scene_dict.get(field_name) or []))
            for field_name in (
                "SceneBeats",
                "SceneObstacles",
                "SceneClues",
                "SceneTransitions",
                "SceneLocations",
                "SceneNPCs",
            )
        },
    }
