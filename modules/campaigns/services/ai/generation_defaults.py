"""Utilities for AI generation defaults."""

from __future__ import annotations

import json
from typing import Any, TypedDict

from db.db import get_campaign_setting, set_campaign_setting

_AI_GENERATION_DEFAULTS_KEY = "ai_generation_defaults_json"


class AIGenerationDefaults(TypedDict):
    main_pc_factions: list[str]
    protected_factions: list[str]
    forbidden_antagonist_factions: list[str]
    tone_hard_constraints: list[str]
    allow_internal_conflict: bool


DEFAULT_AI_GENERATION_DEFAULTS: AIGenerationDefaults = {
    "main_pc_factions": [],
    "protected_factions": [],
    "forbidden_antagonist_factions": [],
    "tone_hard_constraints": [],
    "allow_internal_conflict": False,
}


def load_ai_generation_defaults() -> AIGenerationDefaults:
    """Load AI generation defaults."""
    raw = get_campaign_setting(_AI_GENERATION_DEFAULTS_KEY, None)
    if not raw:
        return dict(DEFAULT_AI_GENERATION_DEFAULTS)

    try:
        payload = json.loads(raw)
    except (TypeError, ValueError):
        return dict(DEFAULT_AI_GENERATION_DEFAULTS)

    if not isinstance(payload, dict):
        return dict(DEFAULT_AI_GENERATION_DEFAULTS)

    return normalize_ai_generation_defaults(payload)


def save_ai_generation_defaults(value: dict[str, Any] | None) -> AIGenerationDefaults:
    """Save AI generation defaults."""
    normalized = normalize_ai_generation_defaults(value)
    set_campaign_setting(_AI_GENERATION_DEFAULTS_KEY, json.dumps(normalized, ensure_ascii=False))
    return normalized


def normalize_ai_generation_defaults(value: dict[str, Any] | None) -> AIGenerationDefaults:
    """Normalize AI generation defaults."""
    value = value or {}

    allow_internal_conflict = value.get("allow_internal_conflict")
    if allow_internal_conflict is None and "allow_optional_conflicts" in value:
        # Migration from legacy key naming used by prompt-generation defaults.
        allow_internal_conflict = value.get("allow_optional_conflicts")

    return {
        "main_pc_factions": _normalize_string_list(value.get("main_pc_factions")),
        "protected_factions": _normalize_string_list(value.get("protected_factions")),
        "forbidden_antagonist_factions": _normalize_string_list(value.get("forbidden_antagonist_factions")),
        "tone_hard_constraints": _normalize_string_list(value.get("tone_hard_constraints")),
        "allow_internal_conflict": bool(allow_internal_conflict),
    }


def _normalize_string_list(values: Any) -> list[str]:
    """Normalize string list."""
    if isinstance(values, str):
        values = [values]
    if not isinstance(values, list):
        return []

    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        # Process each value from values.
        cleaned = str(value or "").strip()
        if not cleaned:
            continue
        key = cleaned.casefold()
        if key in seen:
            continue
        seen.add(key)
        normalized.append(cleaned)

    return normalized
