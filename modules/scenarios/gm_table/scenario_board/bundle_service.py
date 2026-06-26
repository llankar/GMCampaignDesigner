"""Scenario Board bundle resolution helpers.

The board UI only knows about the scenario record and the selected scene.  This
module turns those loose references into canonical campaign entity names using
loaded wrappers and tolerant name matching.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Mapping, Sequence

_ENTITY_TYPES = ("NPCs", "Villains", "Places")
_MAP_NAME_KEYS = ("Name", "Title", "Map", "MapName")
_WORLD_MAP_KEYS = ("WorldMap", "World Map", "WorldMapName", "world_map", "worldMap")
_SCENE_MAP_KEYS = ("Maps", "Map", "SceneMap", "Scene Map", "MapName", "map")


@dataclass(frozen=True)
class ScenarioBundle:
    """Resolved launch bundle for the currently selected scene."""

    scenario_title: str
    scene_title: str
    npcs: tuple[str, ...]
    villains: tuple[str, ...]
    places: tuple[str, ...]
    maps: tuple[str, ...]
    world_maps: tuple[str, ...]


def resolve_scenario_bundle(
    scenario_item: Mapping[str, Any] | None,
    scene: object | None,
    wrappers: Mapping[str, object] | None,
    map_wrapper: object | None,
) -> ScenarioBundle:
    """Resolve scene/scenario references into canonical bundle candidates.

    References can live on either the scenario record or the selected scene.
    Matching is deliberately forgiving: exact case-insensitive aliases win, then
    punctuation-insensitive aliases, then safe substring matches.
    """

    scenario = scenario_item if isinstance(scenario_item, Mapping) else {}
    scene_title = str(getattr(scene, "title", "") or "").strip()
    scenario_title = _label("Scenarios", scenario, fallback="Untitled Scenario")

    wrapped = wrappers or {}
    resolved: dict[str, tuple[str, ...]] = {}
    for entity_type in _ENTITY_TYPES:
        lookup = _build_lookup(entity_type, _safe_load_items(wrapped.get(entity_type)))
        requested = [
            *_coerce_names(scenario.get(entity_type)),
            *_coerce_names(getattr(scene, entity_type.lower(), ())),
        ]
        resolved[entity_type] = _resolve_names(entity_type, requested, lookup)

    map_lookup = _build_lookup(
        "Maps", _safe_load_items(map_wrapper), name_keys=_MAP_NAME_KEYS
    )
    scenario_map_names: list[str] = []
    for key in _SCENE_MAP_KEYS:
        scenario_map_names.extend(_coerce_names(scenario.get(key)))
    scene_map_names = list(_coerce_names(getattr(scene, "maps", ())))
    maps = _resolve_names("Maps", [*scene_map_names, *scenario_map_names], map_lookup)

    world_map_names: list[str] = []
    for key in _WORLD_MAP_KEYS:
        world_map_names.extend(_coerce_names(scenario.get(key)))
    world_maps = _resolve_names("Maps", world_map_names, map_lookup)

    if not world_maps:
        world_maps = _infer_world_map_candidates(map_lookup.records)

    return ScenarioBundle(
        scenario_title=scenario_title,
        scene_title=scene_title,
        npcs=resolved["NPCs"],
        villains=resolved["Villains"],
        places=resolved["Places"],
        maps=maps,
        world_maps=world_maps,
    )


class _Lookup:
    def __init__(
        self,
        entity_type: str,
        records: Sequence[Mapping[str, Any]],
        name_keys: Sequence[str] | None = None,
    ) -> None:
        self.entity_type = entity_type
        self.records = tuple(records)
        self.name_keys = tuple(name_keys or _entity_name_keys(entity_type))
        self.by_alias: dict[str, Mapping[str, Any]] = {}
        self.by_compact: dict[str, Mapping[str, Any]] = {}
        for record in self.records:
            fallback = _label(entity_type, record, fallback="")
            for alias in _record_aliases(record, self.name_keys, fallback=fallback):
                self.by_alias.setdefault(_normalize(alias), record)
                self.by_compact.setdefault(_compact(alias), record)

    def find(self, name: str) -> Mapping[str, Any] | None:
        normalized = _normalize(name)
        if not normalized:
            return None
        compact = _compact(name)
        record = self.by_alias.get(normalized) or self.by_compact.get(compact)
        if record is not None:
            return record
        if len(compact) < 4:
            return None
        matches = [
            candidate
            for alias, candidate in self.by_compact.items()
            if compact in alias or alias in compact
        ]
        return matches[0] if len(matches) == 1 else None


def _safe_load_items(wrapper: object | None) -> list[dict[str, Any]]:
    load_items = getattr(wrapper, "load_items", None)
    if not callable(load_items):
        return []
    try:
        items = load_items()
    except Exception:
        return []
    if not isinstance(items, list):
        return []
    return [item for item in items if isinstance(item, dict)]


def _build_lookup(
    entity_type: str,
    records: Sequence[Mapping[str, Any]],
    name_keys: Sequence[str] | None = None,
) -> _Lookup:
    return _Lookup(entity_type, records, name_keys=name_keys)


def _resolve_names(
    entity_type: str, names: Sequence[str], lookup: _Lookup
) -> tuple[str, ...]:
    resolved: list[str] = []
    seen: set[str] = set()
    for name in names:
        clean = str(name or "").strip()
        if not clean:
            continue
        record = lookup.find(clean)
        display = _label(entity_type, record, fallback=clean) if record else clean
        key = _normalize(display)
        if key and key not in seen:
            seen.add(key)
            resolved.append(display)
    return tuple(resolved)


def _infer_world_map_candidates(
    records: Sequence[Mapping[str, Any]],
) -> tuple[str, ...]:
    candidates: list[str] = []
    for record in records:
        text = " ".join(
            str(record.get(key) or "") for key in ("Type", "Category", "Tags", "Kind")
        )
        if "world" in text.casefold():
            candidates.append(_label("Maps", record, fallback=""))
    return tuple(name for name in candidates if name)


def _coerce_names(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, Mapping):
        return tuple(
            str(value.get(key) or "").strip()
            for key in ("Name", "Title", "name", "title")
            if str(value.get(key) or "").strip()
        )
    if isinstance(value, (list, tuple, set)):
        names: list[str] = []
        for item in value:
            names.extend(_coerce_names(item))
        return tuple(names)
    text = str(value or "").strip()
    if not text:
        return ()
    for delimiter in ("\n", ";", "|", ","):
        if delimiter in text:
            return tuple(part.strip() for part in text.split(delimiter) if part.strip())
    return (text,)


def _entity_name_keys(entity_type: str) -> tuple[str, ...]:
    if entity_type in {"Scenarios", "Informations"}:
        return ("Title", "Name", "title", "name")
    return ("Name", "Title", "name", "title")


def _label(entity_type: str, record: Mapping[str, Any] | None, *, fallback: str) -> str:
    if isinstance(record, Mapping):
        for key in _entity_name_keys(entity_type):
            value = str(record.get(key) or "").strip()
            if value:
                return value
    return str(fallback or "").strip()


def _record_aliases(
    record: Mapping[str, Any], keys: Sequence[str], *, fallback: str
) -> set[str]:
    aliases = {str(record.get(key) or "").strip() for key in keys}
    aliases.add(str(fallback or "").strip())
    return {alias for alias in aliases if alias}


def _normalize(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().casefold())


def _compact(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", _normalize(value))
