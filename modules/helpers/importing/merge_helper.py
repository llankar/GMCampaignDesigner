from __future__ import annotations

from tkinter import messagebox
from typing import Iterable, List, Sequence

from modules.helpers.logging_helper import log_module_import

log_module_import(__name__)


def _normalize_key(value) -> str:
    if value is None:
        return ""
    return str(value).strip().lower()


def find_duplicates(
    existing_items: Sequence[dict], incoming_items: Sequence[dict], key_field: str
) -> list[str]:
    existing_keys = {
        _normalize_key(item.get(key_field))
        for item in existing_items
        if isinstance(item, dict)
    }
    duplicates: list[str] = []
    for item in incoming_items:
        if not isinstance(item, dict):
            continue
        key_value = _normalize_key(item.get(key_field))
        if key_value and key_value in existing_keys:
            duplicates.append(str(item.get(key_field, "")))
    return duplicates


def merge_items(
    existing_items: Sequence[dict],
    incoming_items: Iterable[dict],
    *,
    key_field: str,
    merge_duplicates: bool = True,
) -> list[dict]:
    merged: List[dict] = list(existing_items)
    key_to_index: dict[str, int] = {}

    for idx, item in enumerate(existing_items):
        if not isinstance(item, dict):
            continue
        key_value = _normalize_key(item.get(key_field))
        if key_value:
            key_to_index.setdefault(key_value, idx)

    for item in incoming_items:
        if not isinstance(item, dict):
            merged.append(item)
            continue

        key_value = _normalize_key(item.get(key_field))
        if not key_value:
            merged.append(item)
            continue

        if key_value in key_to_index:
            if merge_duplicates:
                merged[key_to_index[key_value]] = item
        else:
            key_to_index[key_value] = len(merged)
            merged.append(item)

    return merged


def merge_with_confirmation(
    existing_items: Sequence[dict],
    incoming_items: Sequence[dict],
    *,
    key_field: str,
    entity_label: str,
    preview_limit: int = 10,
) -> list[dict]:
    duplicates = find_duplicates(existing_items, incoming_items, key_field)
    if not duplicates:
        return list(existing_items) + list(incoming_items)

    preview_lines = "\n".join(f"- {name}" for name in duplicates[:preview_limit])
    extra = ""
    if len(duplicates) > preview_limit:
        extra = f"\n...and {len(duplicates) - preview_limit} more"

    message = (
        f"Found {len(duplicates)} existing {entity_label} with matching names:\n"
        f"{preview_lines}{extra}\n\n"
        "Choose 'Yes' to merge and overwrite them with the imported versions,\n"
        "or 'No' to keep the existing records and skip the duplicates."
    )

    should_merge = messagebox.askyesno(
        title=f"Merge {entity_label.title()}",
        message=message,
        icon="question",
    )

    return merge_items(
        existing_items,
        incoming_items,
        key_field=key_field,
        merge_duplicates=should_merge,
    )
