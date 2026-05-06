"""Normalize persisted linked-list fields into validator reference fields."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class FieldNormalizationRule:
    """Map one persisted linked-list field to one canonical validator field."""

    entity_type: str
    source_field: str
    canonical_field: str


FIELD_NORMALIZATION_RULES: tuple[FieldNormalizationRule, ...] = (
    FieldNormalizationRule("campaign", "LinkedScenarios", "scenario_refs"),
    FieldNormalizationRule("scenario", "Bases", "base_refs"),
    FieldNormalizationRule("scenario", "Places", "location_refs"),
    FieldNormalizationRule("scenario", "Maps", "map_refs"),
    FieldNormalizationRule("scenario", "NPCs", "npc_refs"),
    FieldNormalizationRule("scenario", "PCs", "pc_refs"),
    FieldNormalizationRule("scenario", "Villains", "villain_refs"),
    FieldNormalizationRule("scenario", "Events", "event_refs"),
    FieldNormalizationRule("scenario", "Creatures", "creature_refs"),
    FieldNormalizationRule("scenario", "Factions", "faction_refs"),
    FieldNormalizationRule("scenario", "Objects", "object_refs"),
    FieldNormalizationRule("scenario", "Books", "book_refs"),
    FieldNormalizationRule("arc", "scenarios", "scenario_refs"),
)

_RULES_BY_TYPE: Mapping[str, tuple[FieldNormalizationRule, ...]] = {
    entity_type: tuple(
        rule for rule in FIELD_NORMALIZATION_RULES if rule.entity_type == entity_type
    )
    for entity_type in {rule.entity_type for rule in FIELD_NORMALIZATION_RULES}
}


def normalize_validator_reference_fields(
    entity_type: str,
    item: Mapping[str, Any],
    *,
    remove_source_fields: bool = True,
) -> dict[str, Any]:
    """Return ``item`` with real linked-list fields projected to canonical refs.

    The normalization is intentionally shallow: reference values are copied as-is
    so strings, IDs, and mapping-shaped references remain compatible with
    ``reference_validator._extract_reference_value()``.
    """

    normalized = dict(item)
    for rule in _RULES_BY_TYPE.get(entity_type, ()):
        if rule.source_field not in normalized:
            continue
        if rule.canonical_field not in normalized:
            normalized[rule.canonical_field] = normalized[rule.source_field]
        if remove_source_fields and rule.source_field != rule.canonical_field:
            normalized.pop(rule.source_field, None)
    return normalized
