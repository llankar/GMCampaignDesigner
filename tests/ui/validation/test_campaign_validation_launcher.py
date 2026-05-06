"""Tests for the campaign validation UI launcher helpers."""

from src.ui.validation import ValidationWizardStatus
from src.ui.validation.campaign_validation_launcher import (
    CampaignHierarchyValidationLauncher,
    build_campaign_validation_hierarchy,
)


class FakeWrapper:
    def __init__(self, items):
        self._items = items

    def load_items(self):
        return list(self._items)


class FakeApp:
    def __init__(self, wrappers):
        self.entity_wrappers = wrappers


def test_build_campaign_validation_hierarchy_normalizes_wrapper_items():
    hierarchy = build_campaign_validation_hierarchy(
        {
            "scenarios": FakeWrapper([{"Title": "Opening Scene", "NPCs": ["Asha"]}]),
            "npcs": FakeWrapper([{"Name": "Asha"}]),
        }
    )

    entities = hierarchy["entities"]

    assert hierarchy["type"] == "campaign"
    assert entities[0]["type"] == "npc"
    assert entities[0]["id"] == "Asha"
    assert entities[1]["type"] == "scenario"
    assert entities[1]["id"] == "Opening Scene"


def test_launcher_instantiates_validator_and_wizard_controller(monkeypatch):
    summaries = []

    def capture_summary(_master, summary):
        summaries.append(summary)

    monkeypatch.setattr(
        "src.ui.validation.campaign_validation_launcher.open_validation_summary_dialog",
        capture_summary,
    )

    launcher = CampaignHierarchyValidationLauncher(FakeApp({}))

    run = launcher.launch()

    assert run is not None
    assert run.graph.issues == ()
    assert run.first_step.status == ValidationWizardStatus.COMPLETED
    assert run.controller.summary.total_issues == 0
    assert summaries == [run.controller.summary]
