"""Contracts for campaign forge."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class CampaignForgeRequest:
    """Input contract for the campaign forge pipeline."""

    foundation: dict[str, Any]
    arcs: list[dict[str, Any]] = field(default_factory=list)
    existing_scenarios: list[dict[str, Any]] | None = None


@dataclass(slots=True)
class CampaignForgeResponse:
    """Structured payload emitted by the campaign forge pipeline."""

    campaign_context: dict[str, Any]
    arcs: list[dict[str, Any]]
    generated_payload: dict[str, Any]
    persistence_payload: dict[str, Any]
    preview_payload: dict[str, Any]
    diagnostics: dict[str, Any] = field(default_factory=dict)

    def to_persistence_payload(self) -> dict[str, Any]:
        """Handle to persistence payload."""
        return dict(self.persistence_payload)

    def to_preview_payload(self) -> dict[str, Any]:
        """Handle to preview payload."""
        return dict(self.preview_payload)
