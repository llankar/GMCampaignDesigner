"""Structured scene field helpers and migrations."""

from __future__ import annotations

import copy
from collections.abc import Iterable
from typing import Any

from modules.helpers.text_helpers import deserialize_possible_json
from modules.scenarios.widgets.scene_sections_parser import parse_scene_body_sections

SCENE_STRUCTURED_SECTION_FIELDS: tuple[dict[str, str], ...] = (
    {"field": "SceneBeats", "key": "key beats", "title": "Key beats", "emoji": "🎯"},
    {"field": "SceneObstacles", "key": "conflicts/obstacles", "title": "Conflicts/obstacles", "emoji": "⚔️"},
    {"field": "SceneClues", "key": "clues/hooks", "title": "Clues/hooks", "emoji": "🧩"},
    {"field": "SceneTransitions", "key": "transitions", "title": "Transitions", "emoji": "🔀"},
    {"field": "SceneLocations", "key": "important locations", "title": "Important locations", "emoji": "📍"},
    {"field": "SceneNPCs", "key": "involved npcs", "title": "Involved NPCs", "emoji": "🧑‍🤝‍🧑"},
)

_SECTION_FIELD_BY_KEY = {item["key"]: item["field"] for item in SCENE_STRUCTURED_SECTION_FIELDS}


def _coerce_string_list(value: Any) -> list[str]:
    """Internal helper for coerce string list."""
    parsed = deserialize_possible_json(value)
    if parsed is None:
        return []
    if isinstance(parsed, dict):
        values: list[str] = []
        for nested in parsed.values():
            values.extend(_coerce_string_list(nested))
        return values
    if isinstance(parsed, (list, tuple, set)):
        values: list[str] = []
        for nested in parsed:
            values.extend(_coerce_string_list(nested))
        return values
    if isinstance(parsed, str):
        candidates = [part.strip() for part in parsed.splitlines() if part.strip()]
        return candidates or ([parsed.strip()] if parsed.strip() else [])
    text = str(parsed).strip()
    return [text] if text else []


def _dedupe_preserve_order(values: Iterable[str]) -> list[str]:
    """Internal helper for dedupe preserve order."""
    seen: set[str] = set()
    deduped: list[str] = []
    for raw in values:
        text = str(raw).strip()
        key = text.lower()
        if not text or key in seen:
            continue
        seen.add(key)
        deduped.append(text)
    return deduped


def normalise_structured_scene_items(value: Any) -> list[str]:
    """Normalise structured scene field values without comma splitting."""
    return _dedupe_preserve_order(_coerce_string_list(value))


def extract_structured_scene_sections(scene_dict: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract display sections from structured scene fields."""
    if not isinstance(scene_dict, dict):
        return []

    sections: list[dict[str, Any]] = []
    for definition in SCENE_STRUCTURED_SECTION_FIELDS:
        items = _dedupe_preserve_order(_coerce_string_list(scene_dict.get(definition["field"])))
        if not items:
            continue
        sections.append(
            {
                "key": definition["key"],
                "title": definition["title"],
                "emoji": definition["emoji"],
                "items": items,
                "raw_text": "\n".join(f"- {item}" for item in items),
            }
        )
    return sections


def parse_scene_sections_with_structured_fallback(scene_dict: dict[str, Any], body_text: str) -> dict[str, Any]:
    """Build parsed section payload, preferring structured scene fields."""
    sections = extract_structured_scene_sections(scene_dict)
    if sections:
        return {
            "intro_text": str(body_text or "").strip(),
            "sections": sections,
            "has_sections": True,
            "source": "structured",
        }
    parsed = parse_scene_body_sections(body_text)
    parsed["source"] = "parser"
    return parsed


def migrate_scene_to_structured_fields(scene_dict: dict[str, Any], body_text: str = "") -> dict[str, Any]:
    """Populate canonical structured section fields from existing scene content."""
    if not isinstance(scene_dict, dict):
        scene_dict = {"Text": str(scene_dict or "")}

    migrated = copy.deepcopy(scene_dict)
    parser_payload = parse_scene_body_sections(body_text)
    parsed_items_by_key = {
        str(section.get("key") or "").lower(): _dedupe_preserve_order(section.get("items") or [])
        for section in (parser_payload.get("sections") or [])
    }

    for definition in SCENE_STRUCTURED_SECTION_FIELDS:
        field_name = definition["field"]
        existing_items = _dedupe_preserve_order(_coerce_string_list(migrated.get(field_name)))
        if existing_items:
            migrated[field_name] = existing_items
            continue
        migrated[field_name] = parsed_items_by_key.get(definition["key"], [])

    return migrated


def get_structured_field_name_for_section_key(section_key: str) -> str | None:
    """Return canonical field name for a parser section key."""
    return _SECTION_FIELD_BY_KEY.get(str(section_key or "").strip().lower())


def compose_scene_text_from_fields(scene_dict: dict[str, Any]) -> str:
    """Compose a legacy text blob from summary + structured fields."""
    if not isinstance(scene_dict, dict):
        return str(scene_dict or "").strip()

    lines: list[str] = []
    summary = str(scene_dict.get("Summary") or "").strip()
    if summary:
        lines.append(summary)

    for definition in SCENE_STRUCTURED_SECTION_FIELDS:
        items = _dedupe_preserve_order(_coerce_string_list(scene_dict.get(definition["field"])))
        if not items:
            continue
        if lines:
            lines.append("")
        lines.append(f"{definition['title']}:")
        lines.extend(f"- {item}" for item in items)

    return "\n".join(lines).strip()
