"""Scenario portrait adapters for the shared SwarmUI portrait service."""
from __future__ import annotations

from typing import Any

from modules.generic.portrait_manager.entity_portrait_actions import (
    ScenarioPortraitEntity,
    copy_portrait_to_campaign,
)
from modules.helpers.swarmui_portrait_service import (
    GeneratedPortraitCandidate,
    GeneratedPortraitResult,
    PortraitGenerationSource,
    SwarmUIPortraitError,
    SwarmUIPortraitSettings,
    build_portrait_prompt,
    cleanup_swarmui,
    generate_portrait_candidates,
    launch_swarmui,
    save_generated_portrait_candidate as save_portrait_candidate,
)


def portrait_source_from_entity(entity: ScenarioPortraitEntity) -> PortraitGenerationSource:
    """Create a generic portrait generation source from a scenario entity."""
    return PortraitGenerationSource(
        name=entity.name,
        record=entity.record,
        key_field=entity.key_field,
    )


def generate_scenario_portrait_candidates(
    entity: ScenarioPortraitEntity,
    settings: SwarmUIPortraitSettings,
    *,
    template: dict[str, Any] | None = None,
    prompt_fields: list[str] | None = None,
) -> list[GeneratedPortraitCandidate]:
    """Generate portrait candidates for a scenario entity using shared service code."""
    return generate_portrait_candidates(
        portrait_source_from_entity(entity),
        settings,
        template=template,
        prompt_fields=prompt_fields,
    )


def save_generated_portrait_candidate(
    entity: ScenarioPortraitEntity,
    candidate: GeneratedPortraitCandidate,
) -> GeneratedPortraitResult:
    """Persist a selected scenario portrait candidate."""
    return save_portrait_candidate(
        portrait_source_from_entity(entity),
        candidate,
        copy_portrait=copy_portrait_to_campaign,
    )


__all__ = [
    "GeneratedPortraitCandidate",
    "GeneratedPortraitResult",
    "PortraitGenerationSource",
    "SwarmUIPortraitError",
    "SwarmUIPortraitSettings",
    "build_portrait_prompt",
    "cleanup_swarmui",
    "generate_scenario_portrait_candidates",
    "launch_swarmui",
    "portrait_source_from_entity",
    "save_generated_portrait_candidate",
]
