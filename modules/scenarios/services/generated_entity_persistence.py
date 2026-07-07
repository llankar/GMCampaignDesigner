"""Persist entities referenced by generated scenarios."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from modules.generic.generic_model_wrapper import GenericModelWrapper


@dataclass(frozen=True)
class GeneratedEntitySaveResult:
    """Summary of entity records created for a generated scenario."""

    npcs_created: list[str]
    places_created: list[str]


class GeneratedScenarioEntityPersistence:
    """Create missing NPC and place records for a generated scenario."""

    def __init__(
        self,
        *,
        npc_wrapper: Any | None = None,
        place_wrapper: Any | None = None,
    ):
        """Initialize the generated entity persistence service."""
        self.npc_wrapper = npc_wrapper or GenericModelWrapper("npcs")
        self.place_wrapper = place_wrapper or GenericModelWrapper("places")

    def save_missing_entities(self, scenario: dict[str, Any]) -> GeneratedEntitySaveResult:
        """Create missing NPCs and places referenced by ``scenario``."""
        title = str(scenario.get("Title") or "").strip()
        npc_names = _coerce_names(scenario.get("NPCs"))
        place_names = _coerce_names(scenario.get("Places"))

        created_npcs = self._save_missing_npcs(npc_names, title)
        created_places = self._save_missing_places(place_names, npc_names, title)

        return GeneratedEntitySaveResult(
            npcs_created=created_npcs,
            places_created=created_places,
        )

    def _save_missing_npcs(self, names: list[str], scenario_title: str) -> list[str]:
        existing = self._load_index(self.npc_wrapper)
        created: list[str] = []
        for name in names:
            key = name.casefold()
            if key in existing:
                continue
            record = {
                "Name": name,
                "Role": "Scenario NPC",
                "Description": _generated_description("NPC", scenario_title),
                "Notes": _generated_notes(scenario_title),
            }
            self.npc_wrapper.save_item(record, key_field="Name")
            existing[key] = record
            created.append(name)
        return created

    def _save_missing_places(
        self,
        names: list[str],
        npc_names: list[str],
        scenario_title: str,
    ) -> list[str]:
        existing = self._load_index(self.place_wrapper)
        created: list[str] = []
        for name in names:
            key = name.casefold()
            if key in existing:
                continue
            record = {
                "Name": name,
                "Description": _generated_description("place", scenario_title),
                "NPCs": npc_names,
                "Notes": _generated_notes(scenario_title),
            }
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


def _coerce_names(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        values: Iterable[Any] = value.split(",")
    elif isinstance(value, (list, tuple, set)):
        values = value
    else:
        values = [value]

    names: list[str] = []
    seen: set[str] = set()
    for item in values:
        name = str(item or "").strip()
        if not name:
            continue
        key = name.casefold()
        if key in seen:
            continue
        seen.add(key)
        names.append(name)
    return names


def _generated_description(entity_label: str, scenario_title: str) -> str:
    if scenario_title:
        return f"Generated from AI scenario '{scenario_title}'. Add details during prep."
    return f"Generated from an AI scenario. Add {entity_label} details during prep."


def _generated_notes(scenario_title: str) -> str:
    if scenario_title:
        return f"Auto-created when saving generated scenario: {scenario_title}"
    return "Auto-created when saving a generated scenario."

