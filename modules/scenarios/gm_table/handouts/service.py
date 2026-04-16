"""Services for collecting scenario-specific player handouts."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping

from modules.helpers.config_helper import ConfigHelper
from modules.helpers.portrait_helper import parse_portrait_value, resolve_portrait_candidate

_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}

# Keep ordering aligned with scenario context link fields.
_LINKED_PORTRAIT_ENTITY_TYPES: tuple[str, ...] = (
    "NPCs",
    "Creatures",
    "Villains",
    "Places",
    "Bases",
    "PCs",
    "Factions",
)


@dataclass(frozen=True)
class HandoutItem:
    """Resolved player-displayable handout descriptor."""

    id: str
    title: str
    entity_type: str
    source_name: str
    path: str
    kind: str  # "portrait" | "map"
    subtitle: str | None = None


def collect_scenario_handouts(
    scenario_item: dict,
    wrappers: Mapping[str, object],
    map_wrapper: object,
) -> list[HandoutItem]:
    """Collect valid handout images linked from a scenario.

    Resolution rules:
    - linked entity names are matched through normalized aliases
    - portrait-like fields are parsed with ``parse_portrait_value``
    - map images are extracted from ``Image``/``image`` fields
    - results are deduplicated by normalized absolute path
    """

    scenario = scenario_item if isinstance(scenario_item, dict) else {}
    records_by_entity = _load_records(wrappers)
    map_records = _safe_load_items(map_wrapper)

    collected: list[tuple[int, str, HandoutItem]] = []

    for entity_type in _LINKED_PORTRAIT_ENTITY_TYPES:
        linked_names = _coerce_name_list(scenario.get(entity_type))
        if not linked_names:
            continue

        wrapper_records = records_by_entity.get(entity_type, [])
        if not wrapper_records:
            continue

        lookup = _build_lookup(entity_type, wrapper_records)
        for link_index, linked_name in enumerate(linked_names):
            record = lookup.get(_normalize_name(linked_name))
            if record is None:
                continue

            display_name = _record_label(entity_type, record, fallback=linked_name)
            candidates = _extract_portrait_candidates(record)
            for candidate in candidates:
                path = _resolve_displayable_image(candidate)
                if not path:
                    continue
                filename = Path(path).name.casefold()
                collected.append(
                    (
                        link_index,
                        filename,
                        HandoutItem(
                            id=f"{entity_type}:{display_name}:{filename}",
                            title=display_name,
                            entity_type=entity_type,
                            source_name=linked_name,
                            path=path,
                            kind="portrait",
                            subtitle=entity_type[:-1] if entity_type.endswith("s") else entity_type,
                        ),
                    )
                )

    map_lookup = _build_lookup("Maps", map_records)
    map_names = _coerce_name_list(scenario.get("Maps"))
    for link_index, map_name in enumerate(map_names):
        record = map_lookup.get(_normalize_name(map_name))
        if record is None:
            continue
        display_name = _record_label("Maps", record, fallback=map_name)
        image_candidates = _extract_map_candidates(record)
        for candidate in image_candidates:
            path = _resolve_displayable_image(candidate)
            if not path:
                continue
            filename = Path(path).name.casefold()
            collected.append(
                (
                    link_index,
                    filename,
                    HandoutItem(
                        id=f"Maps:{display_name}:{filename}",
                        title=display_name,
                        entity_type="Maps",
                        source_name=map_name,
                        path=path,
                        kind="map",
                        subtitle="Map",
                    ),
                )
            )

    return _dedupe_and_sort(collected)


def _safe_load_items(wrapper: object) -> list[dict]:
    load_items = getattr(wrapper, "load_items", None)
    if not callable(load_items):
        return []
    try:
        items = load_items()
    except Exception:
        return []
    return [item for item in items if isinstance(item, dict)] if isinstance(items, list) else []


def _load_records(wrappers: Mapping[str, object]) -> dict[str, list[dict]]:
    records: dict[str, list[dict]] = {}
    for entity_type in _LINKED_PORTRAIT_ENTITY_TYPES:
        records[entity_type] = _safe_load_items(wrappers.get(entity_type))
    return records


def _normalize_name(value) -> str:
    return str(value or "").strip().casefold()


def _entity_name_keys(entity_type: str) -> tuple[str, ...]:
    if entity_type in {"Scenarios", "Informations"}:
        return ("Title", "Name")
    return ("Name", "Title")


def _record_label(entity_type: str, record: dict, *, fallback: str) -> str:
    for key in _entity_name_keys(entity_type):
        value = str(record.get(key) or "").strip()
        if value:
            return value
    return str(fallback or "").strip() or "Unnamed"


def _record_aliases(entity_type: str, record: dict, *, fallback: str = "") -> set[str]:
    aliases: set[str] = set()
    for key in _entity_name_keys(entity_type):
        value = _normalize_name(record.get(key))
        if value:
            aliases.add(value)
    fallback_norm = _normalize_name(fallback)
    if fallback_norm:
        aliases.add(fallback_norm)
    return aliases


def _build_lookup(entity_type: str, records: list[dict]) -> dict[str, dict]:
    lookup: dict[str, dict] = {}
    for record in records:
        fallback = _record_label(entity_type, record, fallback="")
        for alias in _record_aliases(entity_type, record, fallback=fallback):
            lookup.setdefault(alias, record)
    return lookup


def _coerce_name_list(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return [str(item).strip() for item in value if str(item).strip()]

    raw_text = str(value or "").strip()
    if not raw_text:
        return []
    for delimiter in (";", "|", "\n", ","):
        if delimiter in raw_text:
            parts = [part.strip() for part in raw_text.split(delimiter) if part.strip()]
            if parts:
                return parts
    return [raw_text]


def _extract_portrait_candidates(record: dict) -> list[str]:
    candidates: list[str] = []
    for field in ("Portrait", "portrait", "Image", "image"):
        candidates.extend(parse_portrait_value(record.get(field)))
    return candidates


def _extract_map_candidates(record: dict) -> list[str]:
    candidates: list[str] = []
    for field in ("Image", "image"):
        candidates.extend(parse_portrait_value(record.get(field)))
    return candidates


def _resolve_displayable_image(path: str) -> str | None:
    resolved = resolve_portrait_candidate(path, ConfigHelper.get_campaign_dir())
    if not resolved:
        return None
    candidate = Path(resolved).resolve()
    if not candidate.is_file() or candidate.suffix.casefold() not in _IMAGE_EXTENSIONS:
        return None
    return str(candidate)


def _dedupe_and_sort(collected: Iterable[tuple[int, str, HandoutItem]]) -> list[HandoutItem]:
    by_path: dict[str, tuple[int, str, HandoutItem]] = {}
    for link_index, filename, item in collected:
        key = str(Path(item.path).resolve()).casefold()
        existing = by_path.get(key)
        if existing is None or (link_index, filename) < (existing[0], existing[1]):
            by_path[key] = (link_index, filename, item)

    ordered = sorted(by_path.values(), key=lambda entry: (entry[0], entry[1]))
    return [item for _, _, item in ordered]
