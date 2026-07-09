"""Description builders for entities created from AI-generated scenarios."""

from __future__ import annotations

from typing import Any

_ENTITY_FIELDS = ("NPCs", "Places")


def build_entity_description(
    data: dict[str, Any], scenario: dict[str, Any] | None, entity_type: str
) -> str:
    """Return entity-specific descriptive text found in the generated scenario payload.

    The function intentionally never emits template filler.  If the generator only
    supplied a bare name, it falls back to scene excerpts or scenario prose that
    actually came from the AI output.
    """
    for key in ("Description", "Summary", "Details", "Text", "Gist"):
        text = _clean_text(data.get(key))
        if text:
            return text

    name = _entity_name(data)
    scene_excerpt = _description_from_scenes(name, scenario, entity_type)
    if scene_excerpt:
        return scene_excerpt

    contextual = _scenario_context(scenario)
    return contextual


def build_npc_role(data: dict[str, Any], description: str) -> str:
    """Return a non-generic NPC role from generated scenario fields."""
    for key in ("Role", "Function", "Occupation", "Archetype", "Type"):
        role = _clean_text(data.get(key))
        if role and role.casefold() != "scenario npc":
            return role
    return _derive_role_from_description(description)


def linked_npcs_for_place(
    data: dict[str, Any], all_npc_names: list[str], scenario: dict[str, Any] | None
) -> list[str]:
    """Return NPC links for a generated place using explicit or scene-level links."""
    explicit = _names(data.get("NPCs"))
    if explicit:
        return explicit
    place_name = _entity_name(data)
    if not place_name:
        return all_npc_names
    found: list[str] = []
    for scene in _scenes(scenario):
        if (
            place_name not in _names(scene.get("Places"))
            and place_name.casefold() not in _scene_blob(scene).casefold()
        ):
            continue
        for npc in _names(scene.get("NPCs")):
            if npc not in found:
                found.append(npc)
    return found or all_npc_names


def _description_from_scenes(
    name: str, scenario: dict[str, Any] | None, entity_type: str
) -> str:
    if not name:
        return ""
    lines: list[str] = []
    field = "NPCs" if entity_type.casefold() == "npc" else "Places"
    name_key = name.casefold()
    for scene in _scenes(scenario):
        scene_names = [value.casefold() for value in _names(scene.get(field))]
        blob = _scene_blob(scene)
        if name_key not in scene_names and name_key not in blob.casefold():
            continue
        title = _clean_text(scene.get("Title") or scene.get("Name"))
        text = _clean_text(
            scene.get("Text")
            or scene.get("Summary")
            or scene.get("Description")
            or scene.get("Gist")
        )
        if title and text:
            lines.append(f"{title}: {text}")
        elif text:
            lines.append(text)
        elif title:
            lines.append(title)
    return "\n\n".join(lines)


def _scenario_context(scenario: dict[str, Any] | None) -> str:
    if not isinstance(scenario, dict):
        return ""
    parts = [_clean_text(scenario.get("Summary")), _clean_text(scenario.get("Secrets"))]
    return "\n\n".join(part for part in parts if part)


def _derive_role_from_description(description: str) -> str:
    text = _clean_text(description)
    if not text:
        return ""
    first_line = text.splitlines()[0]
    first_sentence = first_line.split(".", 1)[0].strip()
    return first_sentence[:80]


def _scene_blob(scene: dict[str, Any]) -> str:
    chunks = []
    for key, value in scene.items():
        if key in _ENTITY_FIELDS:
            continue
        if isinstance(value, (str, int, float)):
            chunks.append(str(value))
    return "\n".join(chunks)


def _scenes(scenario: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(scenario, dict):
        return []
    scenes = scenario.get("Scenes") or []
    if isinstance(scenes, dict):
        scenes = scenes.get("Scenes") or []
    if not isinstance(scenes, list):
        return []
    return [scene for scene in scenes if isinstance(scene, dict)]


def _entity_name(data: dict[str, Any]) -> str:
    return _clean_text(
        data.get("Name") or data.get("Title") or data.get("name") or data.get("title")
    )


def _names(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, dict):
        return [_entity_name(value)] if _entity_name(value) else []
    if isinstance(value, (list, tuple, set)):
        result: list[str] = []
        for item in value:
            for name in _names(item):
                if name and name not in result:
                    result.append(name)
        return result
    text = _clean_text(value)
    return [text] if text else []


def _clean_text(value: Any) -> str:
    return str(value or "").strip()
