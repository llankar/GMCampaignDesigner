"""Regression tests for campaign forge orchestrator."""

from __future__ import annotations

import pytest

from modules.ai.campaign_forge.contracts import CampaignForgeRequest
from modules.ai.campaign_forge.orchestrator import CampaignForgeOrchestrator
from modules.ai.campaign_forge.validators import CampaignForgeValidationError
from tests.campaigns.fixtures.campaign_forge_payloads import (
    foundation_payload,
    generated_arc_payload,
    generated_scenario_payload,
    malformed_but_normalizable_scenario_payload,
)


class _FakeScenarioWrapper:
    def __init__(self, items=None):
        """Initialize the _FakeScenarioWrapper instance."""
        self.items = list(items or [])

    def load_items(self):
        """Load items."""
        return list(self.items)


class _FakeArcGenerationService:
    def __init__(self, ai_client, scenario_wrapper):
        """Initialize the _FakeArcGenerationService instance."""
        self.ai_client = ai_client
        self.scenario_wrapper = scenario_wrapper

    def generate_arcs(self, foundation):
        """Handle generate arcs."""
        return generated_arc_payload()


class _HappyExpansionService:
    def __init__(self, ai_client):
        """Initialize the _HappyExpansionService instance."""
        self.ai_client = ai_client

    def generate_scenarios(self, foundation, arcs, *, existing_scenarios=None):
        """Handle generate scenarios."""
        return generated_scenario_payload()


class _MalformedExpansionService:
    def __init__(self, ai_client):
        """Initialize the _MalformedExpansionService instance."""
        self.ai_client = ai_client

    def generate_scenarios(self, foundation, arcs, *, existing_scenarios=None):
        """Handle generate scenarios."""
        return malformed_but_normalizable_scenario_payload()


def test_happy_path_full_generation(monkeypatch):
    """Verify that happy path full generation."""
    from modules.ai.campaign_forge import orchestrator as orchestrator_module

    monkeypatch.setattr(orchestrator_module, "ArcGenerationService", _FakeArcGenerationService)
    monkeypatch.setattr(orchestrator_module, "ArcScenarioExpansionService", _HappyExpansionService)

    orchestrator = CampaignForgeOrchestrator(ai_client=object(), scenario_wrapper=_FakeScenarioWrapper())

    result = orchestrator.run(CampaignForgeRequest(foundation=foundation_payload()))

    assert [arc["name"] for arc in result.arcs] == ["Arc Alpha"]
    assert result.generated_payload == result.preview_payload == result.persistence_payload
    assert result.generated_payload["arcs"][0]["scenarios"][0]["Title"] == "Rainmarket Ultimatum"
    assert result.diagnostics["arc_count"] == 1
    assert result.diagnostics["existing_scenario_count"] == 0
    assert result.diagnostics["generated_scenario_count"] == 2
    assert result.diagnostics["generated_scene_count"] >= 0
    assert result.diagnostics["elapsed_ms"] >= 0


def test_malformed_ai_payload_is_normalized_before_validation(monkeypatch):
    """Verify that malformed AI payload is normalized before validation."""
    from modules.ai.campaign_forge import orchestrator as orchestrator_module

    monkeypatch.setattr(orchestrator_module, "ArcGenerationService", _FakeArcGenerationService)
    monkeypatch.setattr(orchestrator_module, "ArcScenarioExpansionService", _MalformedExpansionService)

    orchestrator = CampaignForgeOrchestrator(ai_client=object(), scenario_wrapper=_FakeScenarioWrapper())

    result = orchestrator.run(CampaignForgeRequest(foundation=foundation_payload()))

    assert len(result.generated_payload["arcs"]) == 1
    assert result.generated_payload["arcs"][0]["arc_name"] == "Arc Alpha"
    assert len(result.generated_payload["arcs"][0]["scenarios"]) == 2


def test_arc_scenario_minimum_validation_failures():
    """Verify that arc scenario minimum validation failures."""
    orchestrator = CampaignForgeOrchestrator(ai_client=object(), scenario_wrapper=_FakeScenarioWrapper())

    with pytest.raises(CampaignForgeValidationError, match="at least one linked scenario"):
        orchestrator.run(
            CampaignForgeRequest(
                foundation=foundation_payload(),
                arcs=[
                    {
                        "name": "Arc Beta",
                        "summary": "Escalation",
                        "objective": "Find the mole",
                        "thread": "Conspiracy",
                        "status": "active",
                        "scenarios": [],
                    }
                ],
            )
        )
