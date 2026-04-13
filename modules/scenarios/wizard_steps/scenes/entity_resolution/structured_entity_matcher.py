"""Backward compatible structured scene entity matching helpers."""

from __future__ import annotations

from typing import Any

from modules.scenarios.wizard_steps.scenes.entity_resolution.structured_to_entities import (
    resolve_entities_from_structured,
)


def resolve_scene_entities_from_structured(
    scene_record: dict[str, Any],
    db_indexes: dict[str, dict[str, Any]],
) -> dict[str, list[str]]:
    """Legacy alias for structured scene resolver."""
    return resolve_entities_from_structured(scene_record, db_indexes)
