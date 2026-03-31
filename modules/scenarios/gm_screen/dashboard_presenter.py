"""Utilities for GM screen dashboard presenter."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from modules.helpers.text_helpers import coerce_text

_DEFAULT_ENTITY_LABELS = {
    "Scenarios": "Title",
    "Informations": "Title",
    "Books": "Title",
}

_FOCUS_TYPES = [
    "NPCs",
    "Places",
    "Clues",
    "Factions",
    "Villains",
    "Creatures",
    "Objects",
    "Informations",
    "Books",
    "PCs",
]


def scenario_label(item: dict[str, Any]) -> str:
    """Handle scenario label."""
    return coerce_text(item.get("Title") or item.get("Name") or "Scenario").strip() or "Scenario"


def build_search_index(wrappers: dict[str, Any]) -> tuple[list[dict[str, str]], dict[str, int]]:
    """Build search index."""
    index: list[dict[str, str]] = []
    entity_counts: dict[str, int] = {}

    for entity_type in _FOCUS_TYPES:
        # Process each entity_type from _FOCUS_TYPES.
        wrapper = wrappers.get(entity_type)
        if wrapper is None:
            continue

        try:
            items = wrapper.load_items()
        except Exception:
            continue

        label_key = _DEFAULT_ENTITY_LABELS.get(entity_type, "Name")
        valid_count = 0
        for item in items:
            # Process each item from items.
            label = coerce_text((item or {}).get(label_key)).strip()
            if not label:
                continue
            valid_count += 1
            searchable = f"{label} {entity_type}".lower()
            index.append({"entity_type": entity_type, "label": label, "searchable": searchable})

        entity_counts[entity_type] = valid_count

    index.sort(key=lambda x: x["label"].lower())
    return index, entity_counts


def build_entity_picker_data(index: list[dict[str, str]]) -> dict[str, list[str]]:
    """Build entity picker data."""
    grouped: dict[str, list[str]] = defaultdict(list)
    for item in index:
        grouped[item["entity_type"]].append(item["label"])

    return {entity_type: sorted(set(labels), key=str.lower) for entity_type, labels in grouped.items()}


def group_results(items: list[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    """Group results."""
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for item in items:
        grouped[item["entity_type"]].append(item)
    return dict(grouped)
