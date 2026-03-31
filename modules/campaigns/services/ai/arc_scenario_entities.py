"""Utilities for AI arc scenario entities."""

from __future__ import annotations

from typing import Any

from modules.generic.generic_model_wrapper import GenericModelWrapper


ENTITY_WRAPPER_SPECS: dict[str, dict[str, str]] = {
    "villains": {"wrapper": "villains", "key_field": "Name"},
    "factions": {"wrapper": "factions", "key_field": "Name"},
    "places": {"wrapper": "places", "key_field": "Name"},
    "npcs": {"wrapper": "npcs", "key_field": "Name"},
    "creatures": {"wrapper": "creatures", "key_field": "Name"},
}


def load_existing_entity_catalog(entity_types: list[str] | tuple[str, ...] | None = None) -> dict[str, list[str]]:
    """Load existing linkable entity names for scenario-expansion prompts."""

    catalog: dict[str, list[str]] = {}
    for entity_type in entity_types or tuple(ENTITY_WRAPPER_SPECS):
        # Process each entity_type from entity_types or tuple(ENTITY_WRAPPER_SPECS).
        spec = ENTITY_WRAPPER_SPECS.get(entity_type)
        if not spec:
            continue

        try:
            wrapper = GenericModelWrapper(spec["wrapper"])
            items = wrapper.load_items()
        except Exception:
            catalog[entity_type] = []
            continue

        names: list[str] = []
        seen: set[str] = set()
        for item in items or []:
            # Process each item from items or [].
            if not isinstance(item, dict):
                continue
            name = str(item.get(spec["key_field"]) or "").strip()
            if not name:
                continue
            lowered = name.casefold()
            if lowered in seen:
                continue
            seen.add(lowered)
            names.append(name)
        catalog[entity_type] = sorted(names, key=str.casefold)
    return catalog


def build_existing_entity_lookup(foundation: dict[str, Any]) -> dict[str, set[str]] | None:
    """Convert prompt foundation entity catalogs into casefolded lookup sets."""

    raw_catalog = foundation.get("existing_entities")
    if not isinstance(raw_catalog, dict):
        return None

    lookup: dict[str, set[str]] = {}
    for entity_type in ENTITY_WRAPPER_SPECS:
        # Process each entity_type from ENTITY_WRAPPER_SPECS.
        raw_values = raw_catalog.get(entity_type)
        if not isinstance(raw_values, list):
            lookup[entity_type] = set()
            continue

        lookup[entity_type] = {str(value).strip().casefold() for value in raw_values if str(value).strip()}

    return lookup
