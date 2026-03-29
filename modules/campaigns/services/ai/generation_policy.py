from __future__ import annotations

from typing import Any

from modules.campaigns.services.generation_defaults_mapper import (
    DEFAULT_GENERATION_DEFAULTS_STATE,
    generation_defaults_payload_to_state,
)
from modules.campaigns.services.generation_defaults_service import CampaignGenerationDefaultsService


def resolve_generation_defaults(
    foundation: dict[str, Any] | None = None,
    *,
    generation_defaults_service: CampaignGenerationDefaultsService | None = None,
) -> dict[str, Any]:
    service = generation_defaults_service or CampaignGenerationDefaultsService()
    try:
        loaded_defaults = generation_defaults_payload_to_state(service.load())
    except Exception:
        loaded_defaults = dict(DEFAULT_GENERATION_DEFAULTS_STATE)

    foundation_defaults = generation_defaults_payload_to_state((foundation or {}).get("generation_defaults"))
    merged: dict[str, Any] = dict(loaded_defaults)
    for key in ("main_pc_factions", "protected_factions", "forbidden_antagonist_factions"):
        merged[key] = _merge_string_lists(loaded_defaults.get(key), foundation_defaults.get(key))
    merged["allow_optional_conflicts"] = bool(
        foundation_defaults.get("allow_optional_conflicts", loaded_defaults.get("allow_optional_conflicts", True))
    )
    return generation_defaults_payload_to_state(merged)


def build_hard_constraints_block(generation_defaults: dict[str, Any] | None) -> str:
    normalized = generation_defaults_payload_to_state(generation_defaults)
    lines: list[str] = []
    forbidden = normalized["forbidden_antagonist_factions"]
    allies = _merge_string_lists(normalized["main_pc_factions"], normalized["protected_factions"])

    if forbidden:
        lines.append(
            f"- Never assign these factions as villains/antagonists: {', '.join(forbidden)}."
        )
    if allies:
        lines.append(
            "- Treat these factions as PC allies unless explicitly marked as traitors: "
            f"{', '.join(allies)}."
        )
    if normalized["allow_optional_conflicts"]:
        lines.append(
            "- Optional conflicts involving protected or allied factions are allowed only when the betrayal is explicit and named in scenario text."
        )

    if not lines:
        return ""
    return "Hard constraints:\n" + "\n".join(lines)


def _merge_string_lists(*values: Any) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for value in values:
        for item in (value or []):
            cleaned = str(item or "").strip()
            if not cleaned:
                continue
            key = cleaned.casefold()
            if key in seen:
                continue
            seen.add(key)
            merged.append(cleaned)
    return merged
