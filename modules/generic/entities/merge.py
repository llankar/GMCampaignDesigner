"""Utilities for merging generic entity records."""

from __future__ import annotations

import copy
import json
import os
from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence

from modules.helpers.portrait_helper import parse_portrait_value, serialize_portrait_value


MULTILINE_FIELD_TYPES = {"longtext", "list_longtext", "textarea", "multiline"}
PORTRAIT_FIELD_NAMES = {"portrait", "portraits"}


@dataclass(frozen=True)
class EntityMergeResult:
    """Result of a generic entity merge operation."""

    items: list[dict]
    survivor: dict
    removed: list[dict]


class EntityMergeError(ValueError):
    """Raised when selected entities cannot be merged."""


def merge_selected_entities(
    items: Sequence[dict],
    selected_entities: Sequence[dict],
    template: Mapping | None,
    unique_field: str | None,
) -> EntityMergeResult:
    """Merge selected generic entities into the first selected survivor.

    The first selected entity survives and keeps its unique-field value unchanged.
    Field values are merged in selection order, while non-survivors are removed
    from the returned backing item list.
    """

    selected = [entity for entity in selected_entities if isinstance(entity, dict)]
    if len(selected) < 2:
        raise EntityMergeError("Select at least two entities to merge.")

    survivor_source = selected[0]
    survivor = copy.deepcopy(survivor_source)
    field_types = _field_type_map(template)
    all_keys = _keys_in_selection_order(selected)

    for key in all_keys:
        if unique_field and key == unique_field:
            survivor[key] = copy.deepcopy(survivor_source.get(key, ""))
            continue
        if _is_portrait_field(key):
            survivor[key] = _merge_portrait_values(entity.get(key) for entity in selected)
            continue
        survivor[key] = _merge_generic_field(
            [entity.get(key) for entity in selected],
            field_types.get(key, "text"),
        )

    selected_object_ids = {id(entity) for entity in selected[1:]}
    selected_survivor_id = id(survivor_source)
    survivor_replaced = False
    remaining: list[dict] = []
    for item in items:
        item_id = id(item)
        if item_id == selected_survivor_id and not survivor_replaced:
            remaining.append(survivor)
            survivor_replaced = True
        elif item_id in selected_object_ids:
            continue
        else:
            remaining.append(item)

    if not survivor_replaced:
        remaining.insert(0, survivor)

    return EntityMergeResult(items=remaining, survivor=survivor, removed=list(selected[1:]))


def _field_type_map(template: Mapping | None) -> dict[str, str]:
    fields = template.get("fields", []) if isinstance(template, Mapping) else []
    result: dict[str, str] = {}
    for field in fields:
        if not isinstance(field, Mapping):
            continue
        name = field.get("name")
        if not name:
            continue
        result[str(name)] = str(field.get("type", "text")).strip().lower()
    return result


def _keys_in_selection_order(entities: Sequence[dict]) -> list[str]:
    keys: list[str] = []
    seen: set[str] = set()
    for entity in entities:
        for key in entity.keys():
            if key in seen:
                continue
            seen.add(key)
            keys.append(key)
    return keys


def _is_portrait_field(field_name: str) -> bool:
    return str(field_name or "").strip().lower() in PORTRAIT_FIELD_NAMES


def _merge_generic_field(values: Iterable, field_type: str):
    meaningful = [_normalize_field_value(value) for value in values if not _is_empty_value(value)]
    if not meaningful:
        return ""
    if _is_multiline_field(field_type):
        return "\n".join(_stringify_for_merge(value) for value in meaningful)
    return " ".join(_stringify_for_merge(value).replace("\n", " ") for value in meaningful)


def _is_multiline_field(field_type: str) -> bool:
    return str(field_type or "").strip().lower() in MULTILINE_FIELD_TYPES


def _normalize_field_value(value):
    if isinstance(value, dict) and "text" in value:
        text = value.get("text")
        if len(value) == 1 or isinstance(text, str):
            return text
    return value


def _stringify_for_merge(value) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (list, tuple, set)):
        return "\n".join(_stringify_for_merge(entry) for entry in value if not _is_empty_value(entry)).strip()
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value).strip()


def _merge_portrait_values(values: Iterable) -> str:
    portraits: list[str] = []
    seen: set[str] = set()
    for value in values:
        for portrait in parse_portrait_value(value):
            portrait_text = str(portrait).strip()
            if not portrait_text:
                continue
            key = _portrait_identity(portrait_text)
            if key in seen:
                continue
            seen.add(key)
            portraits.append(portrait_text)
    return serialize_portrait_value(portraits)


def _portrait_identity(value: str) -> str:
    normalized = value.strip().replace("\\", "/")
    normalized = os.path.normpath(normalized).replace("\\", "/")
    return normalized.casefold()


def _is_empty_value(value) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ""
    if isinstance(value, (list, tuple, set, dict)):
        return len(value) == 0
    return False
