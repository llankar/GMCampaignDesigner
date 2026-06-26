"""Data preparation helpers for GM Table scenario board panels."""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Iterable, Mapping

from modules.scenarios.widgets.scene_sections_parser import parse_scene_body_sections

SCENARIO_BOARD_ENTITY_TYPES = (
    "NPCs",
    "PCs",
    "Villains",
    "Creatures",
    "Places",
    "Bases",
    "Factions",
    "Objects",
    "Clues",
    "Informations",
    "Maps",
    "Books",
)


@dataclass(frozen=True)
class ScenarioBoardScene:
    """One scene card prepared for the scenario board."""

    index: int
    title: str
    body: str
    intro_text: str
    sections: tuple[dict[str, Any], ...]
    npcs: tuple[str, ...] = ()
    villains: tuple[str, ...] = ()
    places: tuple[str, ...] = ()
    maps: tuple[str, ...] = ()


@dataclass(frozen=True)
class ScenarioBoardData:
    """Normalized scenario board payload consumed by the UI."""

    title: str
    status: str
    summary: str
    secrets: str
    scenes: tuple[ScenarioBoardScene, ...]
    linked_entities: dict[str, tuple[str, ...]]


def _clean_text(value: Any) -> str:
    """Return a display-safe string without leading or trailing whitespace."""
    return str(value or "").strip()


def _maybe_json_list(value: str) -> list[Any] | None:
    """Return a parsed JSON list when a text field stores list data."""
    text = value.strip()
    if not text or text[0] not in '["':
        return None
    try:
        parsed = json.loads(text)
    except Exception:
        return None
    if isinstance(parsed, list):
        return parsed
    return None


def normalize_list_field(value: Any) -> tuple[str, ...]:
    """Normalize template list/list_longtext fields to a tuple of non-empty strings."""
    if value is None:
        return ()
    if isinstance(value, str):
        parsed = _maybe_json_list(value)
        if parsed is not None:
            return normalize_list_field(parsed)
        return tuple(
            part.strip()
            for part in value.replace("\r\n", "\n").split("\n")
            if part.strip()
        )
    if isinstance(value, dict):
        for key in ("Title", "Name", "title", "name"):
            label = _clean_text(value.get(key))
            if label:
                return (label,)
        return ()
    if isinstance(value, Iterable):
        items: list[str] = []
        for entry in value:
            if isinstance(entry, dict):
                label = ""
                for key in ("Title", "Name", "title", "name"):
                    label = _clean_text(entry.get(key))
                    if label:
                        break
            else:
                label = _clean_text(entry)
            if label:
                items.append(label)
        return tuple(items)
    text = _clean_text(value)
    return (text,) if text else ()


def split_scene_title(scene_text: str, index: int) -> tuple[str, str]:
    """Split a scene longtext block into a card title and body."""
    text = _clean_text(scene_text)
    if not text:
        return f"Scene {index}", ""
    lines = text.splitlines()
    first_line = lines[0].strip()
    if len(lines) > 1 and 0 < len(first_line) <= 90:
        title = first_line.strip("#*: -") or f"Scene {index}"
        return title, "\n".join(lines[1:]).strip()
    for separator in (" — ", " – ", ": "):
        if separator in first_line:
            title, body = first_line.split(separator, 1)
            if title.strip() and len(title.strip()) <= 90:
                remaining = [body.strip(), *lines[1:]]
                return (
                    title.strip("#*: -"),
                    "\n".join(part for part in remaining if part).strip(),
                )
    return f"Scene {index}", text


SCENE_SOURCE_KEYS = ("Scenes", "Scene Flow", "SceneFlow", "scene_flow", "scenes")


def _coerce_scene_entries(item: Mapping[str, Any]) -> list[Any]:
    """Return scene entries from every supported scenario scene field."""
    for key in SCENE_SOURCE_KEYS:
        if key not in item:
            continue
        value = item.get(key)
        if isinstance(value, dict):
            nested = value.get("scenes") or value.get("Scenes")
            if nested is not None:
                value = nested
            else:
                sortable = []
                for scene_key, scene_value in value.items():
                    if isinstance(scene_value, (dict, list, tuple, str)):
                        sortable.append((str(scene_key), scene_value))
                return [
                    entry for _key, entry in sorted(sortable, key=lambda pair: pair[0])
                ]
        if isinstance(value, list):
            return list(value)
        if isinstance(value, str):
            parsed = _maybe_json_list(value)
            if parsed is not None:
                return list(parsed)
            return list(normalize_list_field(value))
    return []


def _scene_field(entry: Mapping[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        if key in entry and entry.get(key) not in (None, ""):
            return entry.get(key)
    return None


def _normalize_scene_entry(entry: Any, index: int) -> ScenarioBoardScene | None:
    if isinstance(entry, Mapping):
        title = _clean_text(
            _scene_field(
                entry,
                (
                    "Title",
                    "title",
                    "Name",
                    "name",
                    "Scene",
                    "scene",
                    "Heading",
                    "heading",
                ),
            )
        )
        body_value = _scene_field(
            entry,
            (
                "Description",
                "description",
                "Body",
                "body",
                "Text",
                "text",
                "Summary",
                "summary",
            ),
        )
        body = _clean_text(body_value)
        if not title:
            title, body = split_scene_title(body, index)
        parsed = parse_scene_body_sections(body)
        return ScenarioBoardScene(
            index=index,
            title=title or f"Scene {index}",
            body=body,
            intro_text=_clean_text(parsed.get("intro_text")),
            sections=tuple(parsed.get("sections") or ()),
            npcs=normalize_list_field(
                _scene_field(
                    entry,
                    (
                        "NPCs",
                        "npcs",
                        "SceneNPCs",
                        "InvolvedNPCs",
                        "Characters",
                        "characters",
                    ),
                )
            ),
            villains=normalize_list_field(
                _scene_field(
                    entry, ("Villains", "villains", "Antagonists", "antagonists")
                )
            ),
            places=normalize_list_field(
                _scene_field(
                    entry,
                    (
                        "Places",
                        "places",
                        "Locations",
                        "locations",
                        "Setting",
                        "setting",
                    ),
                )
            ),
            maps=normalize_list_field(
                _scene_field(
                    entry, ("Maps", "maps", "Map", "map", "SceneMap", "Scene Map")
                )
            ),
        )

    scene_text = _clean_text(entry)
    if not scene_text:
        return None
    title, body = split_scene_title(scene_text, index)
    parsed = parse_scene_body_sections(body or scene_text)
    return ScenarioBoardScene(
        index=index,
        title=title,
        body=body or scene_text,
        intro_text=_clean_text(parsed.get("intro_text")),
        sections=tuple(parsed.get("sections") or ()),
    )


def build_scenario_board_data(
    scenario_item: dict[str, Any] | None,
) -> ScenarioBoardData:
    """Build normalized display data for a scenario board panel."""
    item = scenario_item if isinstance(scenario_item, dict) else {}
    scenes: list[ScenarioBoardScene] = []
    for index, entry in enumerate(_coerce_scene_entries(item), start=1):
        scene = _normalize_scene_entry(entry, index)
        if scene is not None:
            scenes.append(scene)

    linked_entities = {
        entity_type: normalize_list_field(item.get(entity_type))
        for entity_type in SCENARIO_BOARD_ENTITY_TYPES
    }
    linked_entities = {
        entity_type: values for entity_type, values in linked_entities.items() if values
    }

    return ScenarioBoardData(
        title=_clean_text(item.get("Title") or item.get("Name")) or "Untitled Scenario",
        status=_clean_text(item.get("Status")),
        summary=_clean_text(item.get("Summary")),
        secrets=_clean_text(item.get("Secrets")),
        scenes=tuple(scenes),
        linked_entities=linked_entities,
    )
