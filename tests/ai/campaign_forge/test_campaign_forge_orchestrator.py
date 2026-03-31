"""Regression tests for campaign forge orchestrator."""

import pytest

from modules.ai.campaign_forge.contracts import CampaignForgeRequest
from modules.ai.campaign_forge.orchestrator import CampaignForgeOrchestrator
from modules.ai.campaign_forge.validators import CampaignForgeValidationError


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
        return {
            "arcs": [
                {
                    "name": "Arc Alpha",
                    "summary": "Summary",
                    "objective": "Objective",
                    "thread": "Thread",
                    "status": "active",
                    "scenarios": ["Seed Scenario"],
                }
            ]
        }


class _FakeArcScenarioExpansionService:
    instances = []

    def __init__(self, ai_client):
        """Initialize the _FakeArcScenarioExpansionService instance."""
        self.ai_client = ai_client
        self.calls = []
        _FakeArcScenarioExpansionService.instances.append(self)

    def generate_scenarios(self, foundation, arcs, *, existing_scenarios=None):
        """Handle generate scenarios."""
        self.calls.append(
            {
                "foundation": dict(foundation),
                "arcs": [dict(arc) for arc in arcs],
                "existing_scenarios": list(existing_scenarios or []),
            }
        )
        return {
            "arcs": [
                {
                    "arc_name": arc["name"],
                    "scenarios": [
                        {"Title": f"{arc['name']} - A", "Summary": "S1", "Scenes": ["One", "Two", "Three"]},
                        {"Title": f"{arc['name']} - B", "Summary": "S2", "Scenes": ["One", "Two", "Three"]},
                    ],
                }
                for arc in arcs
            ]
        }


def _foundation():
    """Internal helper for foundation."""
    return {
        "name": "Stormfront",
        "genre": "Noir",
        "tone": "Gritty",
        "status": "Active",
        "logline": "A city on the brink.",
        "setting": "Rainmarket",
        "main_objective": "Expose the patron.",
        "stakes": "The city may collapse.",
        "themes": ["Trust", "Corruption"],
    }


def test_orchestrator_uses_provided_arcs_and_db_aware_existing_scenarios(monkeypatch):
    """Verify that orchestrator uses provided arcs and DB aware existing scenarios."""
    from modules.ai.campaign_forge import orchestrator as orchestrator_module

    _FakeArcScenarioExpansionService.instances = []
    monkeypatch.setattr(orchestrator_module, "ArcGenerationService", _FakeArcGenerationService)
    monkeypatch.setattr(orchestrator_module, "ArcScenarioExpansionService", _FakeArcScenarioExpansionService)

    scenario_wrapper = _FakeScenarioWrapper(items=[{"Title": "Existing DB Scenario"}])
    orchestrator = CampaignForgeOrchestrator(ai_client=object(), scenario_wrapper=scenario_wrapper)

    request = CampaignForgeRequest(
        foundation=_foundation(),
        arcs=[
            {
                "name": "Arc Beta",
                "summary": "Escalation.",
                "objective": "Find the mole.",
                "thread": "Conspiracy",
                "status": "active",
                "scenarios": ["Cold Open"],
            }
        ],
    )

    result = orchestrator.run(request)

    assert result.arcs[0]["name"] == "Arc Beta"
    assert result.diagnostics["arc_count"] == 1
    assert result.diagnostics["existing_scenario_count"] == 1
    assert result.generated_payload["arcs"][0]["arc_name"] == "Arc Beta"

    expansion_instance = _FakeArcScenarioExpansionService.instances[0]
    assert expansion_instance.calls[0]["existing_scenarios"] == [{"Title": "Existing DB Scenario"}]


def test_orchestrator_generates_arcs_when_none_are_provided(monkeypatch):
    """Verify that orchestrator generates arcs when none are provided."""
    from modules.ai.campaign_forge import orchestrator as orchestrator_module

    _FakeArcScenarioExpansionService.instances = []
    monkeypatch.setattr(orchestrator_module, "ArcGenerationService", _FakeArcGenerationService)
    monkeypatch.setattr(orchestrator_module, "ArcScenarioExpansionService", _FakeArcScenarioExpansionService)

    orchestrator = CampaignForgeOrchestrator(ai_client=object(), scenario_wrapper=_FakeScenarioWrapper())

    result = orchestrator.run(CampaignForgeRequest(foundation=_foundation()))

    assert result.arcs[0]["name"] == "Arc Alpha"
    assert result.preview_payload == result.persistence_payload


def test_orchestrator_rejects_invalid_generated_structure(monkeypatch):
    """Verify that orchestrator rejects invalid generated structure."""
    from modules.ai.campaign_forge import orchestrator as orchestrator_module

    class _BrokenExpansionService(_FakeArcScenarioExpansionService):
        def generate_scenarios(self, foundation, arcs, *, existing_scenarios=None):
            """Handle generate scenarios."""
            return {"arcs": [{"arc_name": arcs[0]["name"], "scenarios": [{"Title": "Broken"}]}]}

    monkeypatch.setattr(orchestrator_module, "ArcGenerationService", _FakeArcGenerationService)
    monkeypatch.setattr(orchestrator_module, "ArcScenarioExpansionService", _BrokenExpansionService)

    orchestrator = CampaignForgeOrchestrator(ai_client=object(), scenario_wrapper=_FakeScenarioWrapper())

    with pytest.raises(CampaignForgeValidationError):
        orchestrator.run(CampaignForgeRequest(foundation=_foundation()))
