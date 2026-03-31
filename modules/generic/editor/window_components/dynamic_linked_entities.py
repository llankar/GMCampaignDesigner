"""Utilities for window components dynamic linked entities."""

from __future__ import annotations

from modules.generic.editor.window_context import load_entities_list
from modules.generic.entities.linking import resolve_entity_label, resolve_entity_slug


def resolve_linked_entity_source(field: dict) -> tuple[list[str], str]:
    """
    Resolve available options and action label for a dynamic combobox field.

    Supports both modern fields (linked_type) and legacy fields (name).
    """
    linked = (field.get("linked_type") or "").strip()
    fname = (field.get("name") or "").strip()
    key = linked or fname

    slug = resolve_entity_slug(key)
    if not slug:
        return [], f"Add {fname or linked}"

    options = load_entities_list(slug)
    label = f"Add {resolve_entity_label(slug)}"
    return options, label
