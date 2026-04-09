"""Service contracts for GM Screen 2 data access."""

from __future__ import annotations

from typing import Protocol

from modules.scenarios.gm_screen2.domain.models import (
    PanelPayload,
    ScenarioFilter,
    ScenarioSummary,
)


class ScenarioRepository(Protocol):
    """Repository for loading scenario summaries and details."""

    def list_scenarios(self, filters: ScenarioFilter | None = None) -> list[ScenarioSummary]:
        """Return all scenario summaries matching optional filters."""

    def get_scenario(self, scenario_id: str) -> ScenarioSummary | None:
        """Load a single scenario summary by identifier."""


class PanelPayloadProvider(Protocol):
    """Provider responsible for panel payload generation from scenarios."""

    def load_panel_payloads(self, scenario: ScenarioSummary) -> dict[str, PanelPayload]:
        """Return payloads keyed by panel id for a given scenario."""
