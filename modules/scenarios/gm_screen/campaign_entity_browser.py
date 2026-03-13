from __future__ import annotations

from typing import Any

from modules.helpers.template_loader import load_template
from modules.helpers.text_helpers import coerce_text

ENTITY_ORDER = ["NPCs", "Places", "Clues", "Factions", "Villains", "Creatures", "Objects", "Informations", "Books", "PCs"]
_LABEL_KEYS = {"Scenarios": "Title", "Informations": "Title", "Books": "Title"}


def scenario_label(item: dict[str, Any]) -> str:
    return coerce_text(item.get("Title") or item.get("Name") or "Scenario").strip() or "Scenario"


def build_campaign_entity_catalog(wrappers: dict[str, Any]) -> list[dict[str, Any]]:
    """Build a campaign-wide catalog of entities available in wrappers.

    This intentionally excludes the current scenario item itself so the picker
    remains focused on campaign entities.
    """

    catalog: list[dict[str, Any]] = []

    for entity_type in ENTITY_ORDER:
        wrapper = wrappers.get(entity_type)
        if wrapper is None:
            continue
        try:
            items = wrapper.load_items()
        except Exception:
            continue

        label_key = _LABEL_KEYS.get(entity_type, "Name")
        for raw in items:
            item = raw or {}
            cleaned_name = coerce_text(item.get(label_key)).strip()
            if not cleaned_name:
                continue
            catalog.append(
                {
                    "entity_type": entity_type,
                    "name": cleaned_name,
                    "item": item,
                }
            )

    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for entry in catalog:
        key = (entry["entity_type"], entry["name"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(entry)
    return deduped


def build_option_index(catalog: list[dict[str, Any]]) -> tuple[list[str], dict[str, dict[str, Any]]]:
    options: list[str] = []
    index: dict[str, dict[str, Any]] = {}
    for entry in catalog:
        option = f"{entry['entity_type']} • {entry['name']}"
        options.append(option)
        index[option] = entry
    return options, index


def extract_display_fields(entity_type: str, entity_item: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not entity_item:
        return []

    slug = entity_type.lower()
    template = load_template(slug)
    fields: list[dict[str, Any]] = []

    for field in template.get("fields", []):
        field_name = coerce_text(field.get("name")).strip()
        field_type = coerce_text(field.get("type")).strip() or "text"
        if not field_name:
            continue

        value = entity_item.get(field_name)
        if _is_empty(value):
            continue

        if field_type == "list":
            items = [coerce_text(v).strip() for v in (value or []) if coerce_text(v).strip()]
            if not items:
                continue
            fields.append(
                {
                    "name": field_name,
                    "type": "list",
                    "values": items,
                    "linked_type": field.get("linked_type"),
                }
            )
        else:
            fields.append(
                {
                    "name": field_name,
                    "type": field_type,
                    "value": coerce_text(value).strip(),
                }
            )
    return fields


def _is_empty(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, list):
        return len(value) == 0
    return False
