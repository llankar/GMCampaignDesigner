"""Mapping helpers for campaign generation defaults."""
from __future__ import annotations

from typing import Any


DEFAULT_GENERATION_DEFAULTS_STATE = {
    "main_pc_factions": [],
    "protected_factions": [],
    "forbidden_antagonist_factions": [],
    "allow_optional_conflicts": True,
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


def generation_defaults_payload_to_state(payload: dict[str, Any] | None) -> dict[str, Any]:
    """Handle generation defaults payload to state."""
    payload = payload or {}
    return {
        "main_pc_factions": _normalize_string_list(payload.get("main_pc_factions")),
        "protected_factions": _normalize_string_list(payload.get("protected_factions")),
        "forbidden_antagonist_factions": _normalize_string_list(payload.get("forbidden_antagonist_factions")),
        "allow_optional_conflicts": bool(payload.get("allow_optional_conflicts", True)),
    }


def generation_defaults_state_to_payload(state: dict[str, Any] | None) -> dict[str, Any]:
    """Handle generation defaults state to payload."""
    normalized = generation_defaults_payload_to_state(state)
    return {
        "main_pc_factions": normalized["main_pc_factions"],
        "protected_factions": normalized["protected_factions"],
        "forbidden_antagonist_factions": normalized["forbidden_antagonist_factions"],
        "allow_optional_conflicts": normalized["allow_optional_conflicts"],
    }
