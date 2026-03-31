"""Payload helpers for story forge persistence."""
from __future__ import annotations

from modules.ai.story_forge.contracts import StoryForgeResponse


def build_embedded_result_payload(
    response: StoryForgeResponse,
    *,
    campaign_context: dict | None = None,
    arc_context: dict | None = None,
) -> dict:
    """Prepare a wrapper-safe payload that can be consumed by embedding flows."""

    return {
        "scenario": response.to_scenario_payload(),
        "scenario_title": response.title,
        "campaign_context": dict(campaign_context or {}),
        "arc_context": dict(arc_context or {}),
    }
