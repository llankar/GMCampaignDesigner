"""Blueprint helpers for scene."""
from __future__ import annotations

from typing import Any


SCENE_ENTITY_FIELDS: dict[str, str] = {
    "NPCs": "npcs",
    "Creatures": "creatures",
    "Places": "places",
    "Villains": "villains",
    "Factions": "factions",
    "Objects": "objects",
}


class SceneBlueprintError(ValueError):
    """Raised when scene payloads are malformed."""


def normalize_scene_blueprints(raw_scenes: Any) -> tuple[list[str], dict[str, list[str]]]:
    """Normalize generated scenes into playable text blocks and collect scene-level links."""

    if raw_scenes in (None, ""):
        return [], {entity_type: [] for entity_type in SCENE_ENTITY_FIELDS.values()}
    if not isinstance(raw_scenes, list):
        raise SceneBlueprintError("Scenes must be a JSON array")

    normalized_texts: list[str] = []
    scene_entities: dict[str, list[str]] = {entity_type: [] for entity_type in SCENE_ENTITY_FIELDS.values()}

    for index, scene in enumerate(raw_scenes, start=1):
        # Process each (index, scene) from enumerate(raw_scenes, start=1).
        if isinstance(scene, dict):
            # Handle the branch where isinstance(scene, dict).
            scene_text, scene_links = _normalize_structured_scene(scene, index)
            normalized_texts.append(scene_text)
            for entity_type, names in scene_links.items():
                _extend_unique(scene_entities[entity_type], names)
            continue

        text = str(scene or "").strip()
        if not text:
            continue
        normalized_texts.append(text)

    return normalized_texts, scene_entities


def _normalize_structured_scene(scene: dict[str, Any], index: int) -> tuple[str, dict[str, list[str]]]:
    """Normalize structured scene."""
    title = str(scene.get("Title") or scene.get("SceneTitle") or f"Scene {index}").strip() or f"Scene {index}"
    objective = str(scene.get("Objective") or scene.get("Goal") or "").strip()
    setup = str(scene.get("Setup") or scene.get("Opening") or "").strip()
    challenge = str(scene.get("Challenge") or scene.get("Conflict") or "").strip()
    stakes = str(scene.get("Stakes") or "").strip()
    twists = str(scene.get("Twists") or scene.get("Complications") or "").strip()
    gm_notes = str(scene.get("GMNotes") or scene.get("GM Guidance") or scene.get("Guidance") or "").strip()
    outcome = str(scene.get("Outcome") or scene.get("PossibleOutcome") or "").strip()
    summary = str(scene.get("Summary") or scene.get("Description") or "").strip()

    scene_links = _normalize_scene_entities(scene.get("Entities"))

    lines: list[str] = [title]
    if objective:
        lines.append(f"Objective: {objective}")
    if setup:
        lines.append(f"Setup: {setup}")
    if challenge:
        lines.append(f"Challenge: {challenge}")
    if stakes:
        lines.append(f"Stakes: {stakes}")
    if twists:
        lines.append(f"Twists: {twists}")
    if gm_notes:
        lines.append(f"GM Notes: {gm_notes}")
    if outcome:
        lines.append(f"Outcome: {outcome}")
    if summary and summary not in "\n".join(lines):
        lines.append(f"Summary: {summary}")

    for label, entity_type in SCENE_ENTITY_FIELDS.items():
        # Process each (label, entity_type) from SCENE_ENTITY_FIELDS.items().
        names = scene_links[entity_type]
        if names:
            lines.append(f"{label}: {', '.join(names)}")

    condensed = [line for line in lines if line and line.strip()]
    text = "\n".join(condensed).strip()
    if not text:
        raise SceneBlueprintError(f"Scene #{index} is empty")

    return text, scene_links


def _normalize_scene_entities(raw_entities: Any) -> dict[str, list[str]]:
    """Normalize scene entities."""
    links = {entity_type: [] for entity_type in SCENE_ENTITY_FIELDS.values()}
    if not isinstance(raw_entities, dict):
        return links

    for label, entity_type in SCENE_ENTITY_FIELDS.items():
        # Process each (label, entity_type) from SCENE_ENTITY_FIELDS.items().
        values = raw_entities.get(label)
        if values in (None, ""):
            continue
        if not isinstance(values, list):
            continue
        for value in values:
            # Process each value from values.
            cleaned = str(value or "").strip()
            if not cleaned:
                continue
            if cleaned.casefold() in {name.casefold() for name in links[entity_type]}:
                continue
            links[entity_type].append(cleaned)

    return links


def _extend_unique(target: list[str], values: list[str]) -> None:
    """Internal helper for extend unique."""
    existing = {item.casefold() for item in target}
    for value in values:
        # Process each value from values.
        key = value.casefold()
        if key in existing:
            continue
        target.append(value)
        existing.add(key)
