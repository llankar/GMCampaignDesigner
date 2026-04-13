"""Campaign DB index builders for structured scene entity resolution."""

from __future__ import annotations

from typing import Any


DB_ENTITY_TYPE_TO_WRAPPER_KEY = {
    "NPCs": "npcs",
    "Creatures": "creatures",
    "Places": "places",
    "Clues": "clues",
}


def normalise_entity_name(value: Any) -> str:
    """Return a comparable string key for entity names."""
    return str(value or "").strip().casefold()


def _extract_entity_name(item: Any) -> str:
    """Extract a display name from a wrapper record."""
    if isinstance(item, dict):
        raw_name = item.get("Name") or item.get("Title")
    else:
        raw_name = item
    return str(raw_name or "").strip()


def _build_single_entity_index(items: list[Any]) -> dict[str, dict[str, str]]:
    """Build exact and normalised lookups for one entity family."""
    exact: dict[str, str] = {}
    normalised: dict[str, str] = {}
    for item in items or []:
        name = _extract_entity_name(item)
        if not name:
            continue
        exact.setdefault(name, name)
        normalised.setdefault(normalise_entity_name(name), name)
    return {"exact": exact, "normalised": normalised}


def build_campaign_db_indexes(entity_wrappers: dict[str, Any]) -> dict[str, dict[str, dict[str, str]]]:
    """Build campaign indexes with exact + normalised keys for resolver matching."""
    wrappers = entity_wrappers if isinstance(entity_wrappers, dict) else {}
    indexes: dict[str, dict[str, dict[str, str]]] = {}
    for entity_field, wrapper_key in DB_ENTITY_TYPE_TO_WRAPPER_KEY.items():
        wrapper = wrappers.get(wrapper_key)
        items: list[Any] = []
        if wrapper is not None:
            try:
                items = wrapper.load_items() or []
            except Exception:
                items = []
        indexes[entity_field] = _build_single_entity_index(items)
    return indexes

