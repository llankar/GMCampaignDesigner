"""Backward compatible campaign DB index helpers."""

from __future__ import annotations

from typing import Any

from modules.scenarios.wizard_steps.scenes.entity_resolution.structured_to_entities import (
    build_campaign_entity_indexes,
    normalize_name,
)


def normalise_entity_name(value: Any) -> str:
    """Legacy alias for name normalization."""
    return normalize_name(value)


def build_campaign_db_indexes(entity_wrappers: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Legacy alias for campaign entity indexes."""
    return build_campaign_entity_indexes(entity_wrappers)
