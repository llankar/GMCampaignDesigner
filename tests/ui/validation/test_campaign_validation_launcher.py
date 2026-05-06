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


def _campaign_with_arc_reference():
    campaign = _campaign()
    campaign["arc_refs"] = ["Arc One"]
    return campaign


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
    assert entities[1]["npc_refs"] == ["Asha"]
    assert "NPCs" not in entities[1]


def test_build_campaign_validation_hierarchy_normalizes_campaign_linked_scenarios():
    campaign = {
        "id": "c1",
        "Name": "Dragonfall",
        "LinkedScenarios": ["Opening Scene", {"Title": "Hidden Shrine"}],
    }

    hierarchy = build_campaign_validation_hierarchy(
        {
            "campaigns": FakeWrapper([campaign]),
            "scenarios": FakeWrapper([{"Title": "Opening Scene"}]),
        },
        campaign,
    )

    assert hierarchy["scenario_refs"] == ["Opening Scene", {"Title": "Hidden Shrine"}]
    assert "LinkedScenarios" not in hierarchy


def test_build_campaign_validation_hierarchy_builds_selected_campaign_arc_nodes():
    campaign = {
        "id": "c1",
        "Name": "Dragonfall",
        "Arcs": {
            "arcs": [
                {
                    "name": "Opening Arc",
                    "status": "Running",
                    "scenarios": ["Opening Scene", {"Title": "Hidden Shrine"}],
                },
                {
                    "id": "arc-final",
                    "name": "Finale",
                    "scenarios": "Boss Fight",
                },
            ]
        },
    }

    hierarchy = build_campaign_validation_hierarchy(
        {
            "campaigns": FakeWrapper([campaign]),
            "scenarios": FakeWrapper([{"Title": "Opening Scene"}]),
        },
        campaign,
    )

    assert hierarchy["arcs"] == [
        {
            "name": "Opening Arc",
            "status": "In Progress",
            "type": "arc",
            "entity_type": "arc",
            "id": "Opening Arc",
            "scenario_refs": ["Opening Scene", "Hidden Shrine"],
        },
        {
            "id": "arc-final",
            "name": "Finale",
            "status": "Planned",
            "type": "arc",
            "entity_type": "arc",
            "scenario_refs": ["Boss Fight"],
        },
    ]
    assert hierarchy["entities"][0]["entity_type"] == "scenario"


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

    launcher = CampaignHierarchyValidationLauncher(
        FakeApp(wrappers), campaign_selector=selector
    )

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
    messages = []
    summaries = []

    monkeypatch.setattr(
        "src.ui.validation.campaign_validation_launcher.open_validation_summary_dialog",
        lambda *_args, **_kwargs: summaries.append(_args),
    )
    monkeypatch.setattr(
        "tkinter.messagebox.showerror",
        lambda title, message: messages.append((title, message)),
    )
    launcher = CampaignHierarchyValidationLauncher(
        FakeApp({"campaigns": FakeWrapper([_campaign()])}),
        campaign_selector=lambda _master, _campaigns: None,
    )

    assert launcher.launch() is None
    assert launcher.active_run is None
    assert summaries == []
    assert messages == [
        (
            "Campaign required",
            (
                "No campaign was selected for validation. "
                "Select an active campaign, then run validation again."
            ),
        )
    ]


def test_launcher_aborts_when_no_campaigns_exist(monkeypatch):
    messages = []
    summaries = []

    monkeypatch.setattr(
        "src.ui.validation.campaign_validation_launcher.open_validation_summary_dialog",
        lambda *_args, **_kwargs: summaries.append(_args),
    )
    monkeypatch.setattr(
        "tkinter.messagebox.showerror",
        lambda title, message: messages.append((title, message)),
    )
    launcher = CampaignHierarchyValidationLauncher(
        FakeApp({"campaigns": FakeWrapper([])})
    )

    assert launcher.launch() is None
    assert launcher.active_run is None
    assert summaries == []
    assert messages == [
        (
            "Campaign required",
            (
                "No campaign was selected for validation. "
                "Select an active campaign, then run validation again."
            ),
        )
    ]


def test_launcher_reports_unresolved_repository_for_explicit_campaign(monkeypatch):
    messages = []
    summaries = []

    monkeypatch.setattr(
        "src.ui.validation.campaign_validation_launcher.open_validation_summary_dialog",
        lambda *_args, **_kwargs: summaries.append(_args),
    )
    monkeypatch.setattr(
        "tkinter.messagebox.showerror",
        lambda title, message: messages.append((title, message)),
    )
    launcher = CampaignHierarchyValidationLauncher(FakeApp({}))

    assert launcher.launch(_campaign()) is None
    assert launcher.active_run is None
    assert summaries == []
    assert messages == [
        (
            "Campaign data unavailable",
            (
                "The data store or entity services could not be found. "
                "Open or reload a campaign project before running validation again."
            ),
        )
    ]


def test_launcher_reports_bootstrap_exception_without_summary(monkeypatch):
    messages = []
    summaries = []

    monkeypatch.setattr(
        "src.ui.validation.campaign_validation_launcher.open_validation_summary_dialog",
        lambda *_args, **_kwargs: summaries.append(_args),
    )
    monkeypatch.setattr(
        "tkinter.messagebox.showerror",
        lambda title, message: messages.append((title, message)),
    )

    def fail_validation(*_args, **_kwargs):
        raise RuntimeError("validator offline")

    monkeypatch.setattr(
        "src.ui.validation.campaign_validation_launcher.validate_reference_graph",
        fail_validation,
    )
    launcher = CampaignHierarchyValidationLauncher(
        FakeApp({"campaigns": FakeWrapper([_campaign()])})
    )

    assert launcher.launch(_campaign()) is None
    assert launcher.active_run is None
    assert summaries == []
    assert messages == [
        (
            "Validation unavailable",
            (
                "Validation could not start because of an initialization error. "
                "Verify that the project is loaded, then run validation again.\n\n"
                "Technical detail: validator offline"
            ),
        )
    ]


def test_launcher_summary_includes_scan_metrics(monkeypatch):
    summaries = []
    log_messages = []
    monkeypatch.setattr(
        "src.ui.validation.campaign_validation_launcher.open_validation_summary_dialog",
        lambda _master, summary: summaries.append(summary),
    )
    monkeypatch.setattr(
        "src.ui.validation.campaign_validation_launcher.log_info",
        lambda message, **_kwargs: log_messages.append(message),
    )
    launcher = CampaignHierarchyValidationLauncher(
        FakeApp(
            {
                "campaigns": FakeWrapper([_campaign_with_arc_reference()]),
                "arcs": FakeWrapper([{"Name": "Arc One"}]),
                "scenarios": FakeWrapper([{"Name": "Opening"}]),
                "npcs": FakeWrapper([{"Name": "Asha"}]),
            }
        )
    )

    run = launcher.launch(_campaign_with_arc_reference())

    assert run is not None
    assert run.graph.diagnostics.visited_references == len(run.graph.references)
    summary = summaries[0]
    assert summary.metrics.entities_visited == len(run.graph.entities) == 4
    assert summary.metrics.references_checked == len(run.graph.references) == 1
    assert summary.metrics.elapsed_seconds >= 0
    assert any(run.graph.debug_summary in message for message in log_messages)
    assert any(
        "entities_visited=4" in message and "references_checked=1" in message
        for message in log_messages
    )
    diagnostics = run.graph.diagnostics
    assert any(
        f"campaigns={diagnostics.visited_campaigns}" in message
        and f"arcs={diagnostics.visited_arcs}" in message
        and f"scenarios={diagnostics.visited_scenarios}" in message
        and f"references={diagnostics.visited_references}" in message
        for message in log_messages
    )


def test_build_campaign_validation_hierarchy_reports_lightweight_phases():
    phases = []

    class FakeProgress:
        def set_phase(self, phase):
            phases.append(phase)

    build_campaign_validation_hierarchy(
        {
            "campaigns": FakeWrapper([_campaign()]),
            "arcs": FakeWrapper([]),
            "scenarios": FakeWrapper([]),
        },
        _campaign(),
        progress=FakeProgress(),
    )

    assert "Scanning arcs…" in phases
    assert "Scanning scenarios…" in phases
