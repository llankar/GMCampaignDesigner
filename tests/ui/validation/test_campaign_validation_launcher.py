"""Tests for the campaign validation UI launcher helpers."""

from src.ui.validation import ValidationWizardStatus
from src.ui.validation.campaign_validation_launcher import (
    CampaignHierarchyValidationLauncher,
    build_campaign_validation_hierarchy,
    load_campaign_options,
)


class FakeWrapper:
    def __init__(self, items):
        self._items = items

    def load_items(self):
        return list(self._items)


class FakeApp:
    def __init__(self, wrappers):
        self.entity_wrappers = wrappers


def _campaign():
    return {"id": "c1", "Name": "Dragonfall"}


def test_build_campaign_validation_hierarchy_normalizes_wrapper_items():
    hierarchy = build_campaign_validation_hierarchy(
        {
            "campaigns": FakeWrapper([_campaign()]),
            "scenarios": FakeWrapper([{"Title": "Opening Scene", "NPCs": ["Asha"]}]),
            "npcs": FakeWrapper([{"Name": "Asha"}]),
        },
        _campaign(),
    )

    entities = hierarchy["entities"]

    assert hierarchy["type"] == "campaign"
    assert hierarchy["id"] == "c1"
    assert hierarchy["name"] == "Dragonfall"
    assert entities[0]["type"] == "npc"
    assert entities[0]["id"] == "Asha"
    assert entities[1]["type"] == "scenario"
    assert entities[1]["id"] == "Opening Scene"


def test_load_campaign_options_reads_campaigns_wrapper_only():
    options = load_campaign_options(
        {
            "campaigns": FakeWrapper([_campaign()]),
            "npcs": FakeWrapper([{"Name": "Asha"}]),
        }
    )

    assert len(options) == 1
    assert options[0].campaign_id == "c1"
    assert options[0].label == "Dragonfall"
    assert options[0].item == _campaign()


def test_launcher_opens_selector_for_global_action_and_passes_campaign(monkeypatch):
    summaries = []

    def capture_summary(_master, summary):
        summaries.append(summary)

    monkeypatch.setattr(
        "src.ui.validation.campaign_validation_launcher.open_validation_summary_dialog",
        capture_summary,
    )

    wrappers = {"campaigns": FakeWrapper([_campaign()])}
    selector_options = []

    def selector(_master, campaigns):
        selector_options.extend(campaigns)
        return campaigns[0]

    launcher = CampaignHierarchyValidationLauncher(FakeApp(wrappers), campaign_selector=selector)

    run = launcher.launch()

    assert run is not None
    assert run.campaign.campaign_id == "c1"
    assert run.graph.campaign == _campaign()
    assert run.controller.campaign == _campaign()
    assert run.graph.issues == ()
    assert run.first_step.status == ValidationWizardStatus.COMPLETED
    assert run.controller.summary.total_issues == 0
    assert selector_options[0].campaign_id == "c1"
    assert summaries == [run.controller.summary]


def test_launcher_accepts_campaign_screen_selection_without_global_dialog(monkeypatch):
    monkeypatch.setattr(
        "src.ui.validation.campaign_validation_launcher.open_validation_summary_dialog",
        lambda *_args, **_kwargs: None,
    )
    selector_calls = []
    launcher = CampaignHierarchyValidationLauncher(
        FakeApp({"campaigns": FakeWrapper([_campaign()])}),
        campaign_selector=lambda _master, campaigns: selector_calls.append(campaigns),
    )

    run = launcher.launch(_campaign())

    assert run is not None
    assert run.campaign.campaign_id == "c1"
    assert selector_calls == []


def test_launcher_aborts_cleanly_when_user_cancels_selection(monkeypatch):
    monkeypatch.setattr(
        "src.ui.validation.campaign_validation_launcher.open_validation_summary_dialog",
        lambda *_args, **_kwargs: None,
    )
    launcher = CampaignHierarchyValidationLauncher(
        FakeApp({"campaigns": FakeWrapper([_campaign()])}),
        campaign_selector=lambda _master, _campaigns: None,
    )

    assert launcher.launch() is None
    assert launcher.active_run is None


def test_launcher_aborts_when_no_campaigns_exist(monkeypatch):
    messages = []

    monkeypatch.setattr(
        "tkinter.messagebox.showinfo",
        lambda title, message: messages.append((title, message)),
    )
    launcher = CampaignHierarchyValidationLauncher(FakeApp({}))

    assert launcher.launch() is None
    assert launcher.active_run is None
    assert messages == [
        (
            "Aucune campagne",
            (
                "Aucune campagne n’existe encore. Créez ou importez une campagne "
                "avant de lancer la validation."
            ),
        )
    ]
