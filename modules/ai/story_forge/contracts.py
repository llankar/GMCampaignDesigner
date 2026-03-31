"""Contracts for story forge."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class StoryForgeRequest:
    """Input payload used by Story Forge to draft a scenario."""

    brief: str
    campaign_name: str = ""
    campaign_summary: str = ""
    arc_name: str = ""
    arc_summary: str = ""
    arc_objective: str = ""
    arc_thread: str = ""
    existing_scenarios: list[str] = field(default_factory=list)
    entity_catalog: dict[str, list[str]] = field(default_factory=dict)


@dataclass(slots=True)
class StoryForgeResponse:
    """Normalized scenario payload returned by Story Forge."""

    title: str
    summary: str
    secrets: str
    scenes: list[dict[str, Any]]
    entities: dict[str, list[str]]
    raw_steps: dict[str, Any] = field(default_factory=dict)

    def to_scenario_payload(self) -> dict[str, Any]:
        """Handle to scenario payload."""
        payload = {
            "Title": self.title,
            "Summary": self.summary,
            "Secrets": self.secrets,
            "Secret": self.secrets,
            "Scenes": self.scenes,
        }
        payload.update(self.entities)
        return payload
