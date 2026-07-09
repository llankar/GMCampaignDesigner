"""Persist entities referenced by generated scenarios."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Iterable

from modules.generic.generic_model_wrapper import GenericModelWrapper
from modules.importers.pdf_entity_importer import to_longtext
from modules.scenarios.services.generated_entity_descriptions import (
    build_entity_description,
    build_npc_role,
    linked_npcs_for_place,
)


@dataclass(frozen=True)
class GeneratedEntitySaveResult:
    """Summary of entity records created for a generated scenario."""

    npcs_created: list[str]
    places_created: list[str]


class GeneratedScenarioEntityPersistence:
    """Create missing NPC and place records for a generated scenario.

    The AI prompt generator can return either simple name lists or richer entity
    dictionaries.  Persisting follows the PDF importer shape so generated NPCs
    and places open with useful rich-text fields instead of placeholder text.
    """

    def __init__(
        self,
        *,
        npc_wrapper: Any | None = None,
        place_wrapper: Any | None = None,
    ):
        """Initialize the generated entity persistence service."""
        self.npc_wrapper = npc_wrapper or GenericModelWrapper("npcs")
        self.place_wrapper = place_wrapper or GenericModelWrapper("places")

    def save_missing_entities(
        self,
        scenario: dict[str, Any],
        entity_source: dict[str, Any] | None = None,
    ) -> GeneratedEntitySaveResult:
        """Create missing NPCs and places referenced by ``scenario``.

        ``scenario`` is the DB-ready scenario record. ``entity_source`` may be
        the raw normalized AI payload containing richer NPC/place dictionaries.
        """
        source = entity_source if isinstance(entity_source, dict) else scenario
        title = str(scenario.get("Title") or source.get("Title") or "").strip()
        npc_records = _entity_records(source.get("NPCs") or scenario.get("NPCs"))
        place_records = _entity_records(source.get("Places") or scenario.get("Places"))
        npc_names = _entity_names(npc_records)
        created_npcs = self._save_missing_npcs(npc_records, title, source)
        created_places = self._save_missing_places(
            place_records, npc_names, title, source
        )

        # If only scene-level entities were present, keep the old name-based
        # behavior as a final fallback.
        if not npc_records:
            created_npcs = self._save_missing_npcs(
                _entity_records(scenario.get("NPCs")), title, source
            )
        if not place_records:
            created_places = self._save_missing_places(
                _entity_records(scenario.get("Places")), npc_names, title, source
            )

        return GeneratedEntitySaveResult(
            npcs_created=created_npcs,
            places_created=created_places,
        )

    def _save_missing_npcs(
        self,
        records: list[dict[str, Any]],
        scenario_title: str,
        scenario_source: dict[str, Any] | None = None,
    ) -> list[str]:
        existing = self._load_index(self.npc_wrapper)
        created: list[str] = []
        for data in records:
            name = str(data.get("Name") or data.get("Title") or "").strip()
            if not name:
                continue
            key = name.casefold()
            if key in existing:
                continue
            record = _build_npc_record(data, scenario_title, scenario_source)
            self.npc_wrapper.save_item(record, key_field="Name")
            existing[key] = record
            created.append(name)
        return created

    def _save_missing_places(
        self,
        records: list[dict[str, Any]],
        npc_names: list[str],
        scenario_title: str,
        scenario_source: dict[str, Any] | None = None,
    ) -> list[str]:
        existing = self._load_index(self.place_wrapper)
        created: list[str] = []
        for data in records:
            name = str(data.get("Name") or data.get("Title") or "").strip()
            if not name:
                continue
            key = name.casefold()
            if key in existing:
                continue
            record = _build_place_record(
                data, npc_names, scenario_title, scenario_source
            )
            self.place_wrapper.save_item(record, key_field="Name")
            existing[key] = record
            created.append(name)
        return created

    @staticmethod
    def _load_index(wrapper: Any) -> dict[str, dict[str, Any]]:
        try:
            items = wrapper.load_items()
        except Exception:
            items = []
        index: dict[str, dict[str, Any]] = {}
        for item in items or []:
            if not isinstance(item, dict):
                continue
            name = str(item.get("Name") or "").strip()
            if name:
                index[name.casefold()] = dict(item)
        return index


def scenario_entity_names(value: Any) -> list[str]:
    """Return unique entity names suitable for scenario link fields."""
    return _entity_names(_entity_records(value))


def _entity_records(value: Any) -> list[dict[str, Any]]:
    if value is None:
        return []
    if isinstance(value, dict):
        name = (
            value.get("Name")
            or value.get("Title")
            or value.get("name")
            or value.get("title")
        )
        record = {str(k): v for k, v in value.items()}
        if name and not record.get("Name"):
            record["Name"] = name
        return [record] if record.get("Name") else []
    if isinstance(value, str):
        values: Iterable[Any] = value.split(",")
    elif isinstance(value, (list, tuple, set)):
        values = value
    else:
        values = [value]

    records: list[dict[str, Any]] = []
    for item in values:
        if isinstance(item, dict):
            records.extend(_entity_records(item))
            continue
        name = str(item or "").strip()
        if name:
            records.append({"Name": name})
    return _dedupe_records(records)


def _entity_names(records: list[dict[str, Any]]) -> list[str]:
    return [
        str(record.get("Name") or "").strip()
        for record in records
        if str(record.get("Name") or "").strip()
    ]


def _dedupe_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for record in records:
        name = str(record.get("Name") or "").strip()
        key = name.casefold()
        if not name or key in seen:
            continue
        seen.add(key)
        result.append(record)
    return result


def _build_npc_record(
    data: dict[str, Any],
    scenario_title: str,
    scenario_source: dict[str, Any] | None = None,
) -> dict[str, Any]:
    description = build_entity_description(data, scenario_source, "npc")
    description, description_atouts = _split_atouts_section(description)
    traits = _merge_traits_with_atouts(data.get("Traits", ""), description_atouts)
    return {
        "Name": str(data.get("Name") or data.get("Title") or "Unnamed").strip(),
        "Role": build_npc_role(data, description),
        "Description": to_longtext(description),
        "Secret": to_longtext(data.get("Secret") or data.get("Secrets") or ""),
        "Quote": data.get("Quote", ""),
        "RoleplayingCues": to_longtext(data.get("RoleplayingCues", "")),
        "Personality": to_longtext(data.get("Personality", "")),
        "Motivation": to_longtext(data.get("Motivation", "")),
        "Background": to_longtext(data.get("Background", "")),
        "Traits": to_longtext(traits),
        "Genre": data.get("Genre", ""),
        "Factions": data.get("Factions", []),
        "Objects": data.get("Objects", []),
        "Portrait": data.get("Portrait", ""),
        "Notes": _generated_notes(scenario_title),
    }


def _build_place_record(
    data: dict[str, Any],
    npc_names: list[str],
    scenario_title: str,
    scenario_source: dict[str, Any] | None = None,
) -> dict[str, Any]:
    description = build_entity_description(data, scenario_source, "place")
    npcs = linked_npcs_for_place(data, npc_names, scenario_source)
    return {
        "Name": str(data.get("Name") or data.get("Title") or "Unnamed").strip(),
        "Description": to_longtext(description),
        "NPCs": npcs,
        "PlayerDisplay": data.get("PlayerDisplay", False),
        "Secrets": to_longtext(data.get("Secrets", "")),
        "Portrait": data.get("Portrait", ""),
        "Notes": _generated_notes(scenario_title),
    }


def _split_atouts_section(text: str) -> tuple[str, str]:
    """Move a trailing Atouts section out of NPC descriptions and into traits."""
    source = str(text or "").strip()
    if not source:
        return "", ""
    match = re.search(r"(?im)^\s*(?:[*#-]\s*)?Atouts\s*:\s*", source)
    if not match:
        return source, ""
    description = source[: match.start()].rstrip()
    atouts = source[match.start() :].strip()
    return description, atouts


def _merge_traits_with_atouts(traits: Any, atouts: str) -> str:
    """Append extracted Atouts to the Traits field without losing existing traits."""
    base = str(traits or "").strip()
    extra = str(atouts or "").strip()
    if not extra:
        return base
    if not base:
        return extra
    if extra.casefold() in base.casefold():
        return base
    return f"{base}\n\n{extra}"


def _generated_notes(scenario_title: str) -> str:
    if scenario_title:
        return f"Auto-created when saving generated scenario: {scenario_title}"
    return "Auto-created when saving a generated scenario."
