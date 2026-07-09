"""Reusable portrait helpers for scenario-linked entity portrait management."""
from __future__ import annotations
import shutil, time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable
from modules.generic.generic_model_wrapper import GenericModelWrapper
from modules.helpers.config_helper import ConfigHelper
from modules.helpers.portrait_helper import parse_portrait_value, primary_portrait, resolve_portrait_candidate, serialize_portrait_value

SCENARIO_PORTRAIT_LINK_FIELDS = ("NPCs", "Places", "Creatures", "Villains", "Factions", "Objects", "PCs", "Clues", "Informations", "Books")
SCENARIO_FIELD_TO_ENTITY_TYPE = {"NPCs":"npcs", "Places":"places", "Creatures":"creatures", "Villains":"villains", "Factions":"factions", "Objects":"objects", "PCs":"pcs", "Clues":"clues", "Informations":"informations", "Books":"books"}

@dataclass
class ScenarioPortraitEntity:
    """A scenario-linked entity and the model wrapper that persists it."""
    entity_type: str
    name: str
    record: dict[str, Any]
    wrapper: GenericModelWrapper
    source_field: str = ""
    @property
    def key_field(self) -> str:
        return self.wrapper._infer_key_field()

def _coerce_link_names(value: Any) -> list[str]:
    """Return display names from a scenario relationship field value."""
    if value in (None, ""):
        return []
    if isinstance(value, dict):
        candidates: Iterable[Any] = value.values()
    elif isinstance(value, (list, tuple, set)):
        candidates = value
    else:
        candidates = str(value).split(",")
    names: list[str] = []
    for candidate in candidates:
        if isinstance(candidate, dict):
            raw = candidate.get("Name") or candidate.get("Title") or candidate.get("name") or candidate.get("title") or candidate.get("text")
        else:
            raw = candidate
        name = str(raw or "").strip()
        if name and name not in names:
            names.append(name)
    return names

def extract_scenario_linked_entity_names(scenario: dict[str, Any]) -> list[tuple[str, str, str]]:
    """Extract ``(entity_type, name, source_field)`` links from a scenario record."""
    links: list[tuple[str, str, str]] = []
    seen: set[tuple[str, str]] = set()
    for field in SCENARIO_PORTRAIT_LINK_FIELDS:
        entity_type = SCENARIO_FIELD_TO_ENTITY_TYPE[field]
        for name in _coerce_link_names(scenario.get(field)):
            key = (entity_type, name.casefold())
            if key in seen:
                continue
            seen.add(key)
            links.append((entity_type, name, field))
    return links

def resolve_scenario_linked_entities(scenario: dict[str, Any], wrapper_factory: Callable[[str], GenericModelWrapper] = GenericModelWrapper) -> list[ScenarioPortraitEntity]:
    """Resolve linked scenario names into entity records using GenericModelWrapper."""
    wrappers: dict[str, GenericModelWrapper] = {}
    cache: dict[str, dict[str, dict[str, Any]]] = {}
    resolved: list[ScenarioPortraitEntity] = []
    for entity_type, name, source_field in extract_scenario_linked_entity_names(scenario):
        wrapper = wrappers.setdefault(entity_type, wrapper_factory(entity_type))
        if entity_type not in cache:
            key_field = wrapper._infer_key_field()
            cache[entity_type] = {str(item.get(key_field) or item.get("Name") or item.get("Title") or "").casefold(): item for item in wrapper.load_items()}
        record = cache[entity_type].get(name.casefold())
        if record:
            resolved.append(ScenarioPortraitEntity(entity_type, name, record, wrapper, source_field))
    return resolved

def portrait_paths(record: dict[str, Any]) -> list[str]:
    """Return parsed portrait paths from an entity record."""
    return [path for path in parse_portrait_value(record.get("Portrait", "")) if path]

def has_resolved_portrait(record: dict[str, Any], campaign_dir: str | None = None) -> bool:
    """Return True when an entity has a primary portrait that resolves to an existing asset."""
    campaign_dir = campaign_dir or ConfigHelper.get_campaign_dir()
    primary = primary_portrait(portrait_paths(record))
    return bool(primary and resolve_portrait_candidate(primary, campaign_dir))

def portrait_status(record: dict[str, Any], campaign_dir: str | None = None) -> str:
    """Return a compact UI status for an entity portrait."""
    paths = portrait_paths(record)
    if not paths:
        return "Missing"
    if has_resolved_portrait(record, campaign_dir):
        return "Ready"
    return "Missing file"

def missing_portrait_indices(entities: list[ScenarioPortraitEntity], campaign_dir: str | None = None) -> list[int]:
    """Return indexes of entities without a resolvable portrait, preserving scenario order."""
    return [index for index, entity in enumerate(entities) if not has_resolved_portrait(entity.record, campaign_dir)]

def campaign_relative_path(path: str) -> str:
    """Normalize a path relative to the active campaign directory when possible."""
    if not path:
        return ""
    candidate = Path(path)
    if candidate.is_absolute():
        try:
            return candidate.resolve().relative_to(Path(ConfigHelper.get_campaign_dir()).resolve()).as_posix()
        except ValueError:
            return candidate.as_posix()
    return candidate.as_posix()

def copy_portrait_to_campaign(src_path: str, entity_name: str) -> str:
    """Copy a selected portrait into the campaign portrait folder."""
    campaign_dir = Path(ConfigHelper.get_campaign_dir())
    portrait_folder = campaign_dir / "assets" / "portraits"
    portrait_folder.mkdir(parents=True, exist_ok=True)
    safe_name = "".join(ch if ch.isalnum() or ch in {"_", "-"} else "_" for ch in entity_name) or "entity"
    source = Path(src_path)
    safe_stem = "".join(ch if ch.isalnum() or ch in {"_", "-"} else "_" for ch in source.stem) or "portrait"
    dest = portrait_folder / f"{safe_name}_{safe_stem}_{time.time_ns()}{source.suffix.lower()}"
    shutil.copy(str(source), dest)
    return campaign_relative_path(str(dest))

def set_entity_portraits(entity: ScenarioPortraitEntity, paths: list[str]) -> None:
    """Persist an entity's portrait list through its wrapper."""
    entity.record["Portrait"] = serialize_portrait_value([campaign_relative_path(path) for path in paths if path])
    entity.wrapper.save_item(entity.record)
