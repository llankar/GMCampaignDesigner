"""Tests for the campaign validation UI launcher helpers."""

from src.ui.validation import (
    ValidationWizardController,
    ValidationWizardIssue,
    ValidationWizardStatus,
    resolve_reference_for_issue,
    resolve_target_for_issue,
)
from src.validation import IssueType, validate_reference_graph
from src.ui.validation.campaign_validation_launcher import (
    CampaignValidationRun,
    CampaignHierarchyValidationLauncher,
    build_campaign_validation_hierarchy,
    campaign_option_from_item,
    load_campaign_options,
)
from src.ui.validation.campaign_scenario_entity_hierarchy import (
    campaign_validation_reference_config,
    discover_scenario_linked_entity_rules,
)
from src.validation import FIELD_EXPECTED_TYPES


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


def _invalid_hierarchy_run():
    hierarchy = {
        "type": "campaign",
        "id": "C1",
        "name": "Dragonfall",
        "arcs": [
            {
                "type": "arc",
                "id": "A1",
                "name": "Main Arc",
                "location_refs": ["Sibling Place"],
            },
            {
                "type": "arc",
                "id": "A2",
                "name": "Sibling Arc",
                "locations": [
                    {"type": "location", "id": "L2", "name": "Sibling Place"}
                ],
            },
        ],
    }
    graph = validate_reference_graph(hierarchy, campaign={"id": "C1"})
    controller = ValidationWizardController(
        tuple(
            ValidationWizardIssue(
                issue=issue,
                reference=resolve_reference_for_issue(issue, graph.references),
                target=resolve_target_for_issue(issue, graph.entities),
            )
            for issue in graph.issues
        ),
        campaign=graph.campaign,
    )
    first_step = controller.start()

    assert first_step.issue is not None
    assert first_step.issue.issue_type == IssueType.INVALID_HIERARCHY

    return CampaignValidationRun(
        campaign=campaign_option_from_item(_campaign()),
        graph=graph,
        controller=controller,
        first_step=first_step,
    )


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
    assert entities == [
        {
            "Name": "Asha",
            "type": "npc",
            "entity_type": "npc",
            "id": "Asha",
            "name": "Asha",
        }
    ]


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


def test_campaign_linked_scenarios_accept_scenarios_attached_under_arcs():
    campaign = {
        "id": "c1",
        "Name": "Dragonfall",
        "LinkedScenarios": ["Opening Scene"],
        "Arcs": {"arcs": [{"name": "Opening Arc", "scenarios": ["Opening Scene"]}]},
    }

    hierarchy = build_campaign_validation_hierarchy(
        {
            "campaigns": FakeWrapper([campaign]),
            "scenarios": FakeWrapper([{"Title": "Opening Scene"}]),
        },
        campaign,
    )
    graph = validate_reference_graph(hierarchy, campaign=campaign)

    assert hierarchy["scenario_refs"] == ["Opening Scene"]
    assert hierarchy["arcs"][0]["scenario_refs"] == []
    assert [scenario["id"] for scenario in hierarchy["arcs"][0]["scenarios"]] == [
        "Opening Scene"
    ]
    assert [reference.field_path for reference in graph.references] == [
        "campaign.scenario_refs"
    ]
    assert graph.issues == ()


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
            "scenario_refs": ["Hidden Shrine"],
            "scenarios": [
                {
                    "Title": "Opening Scene",
                    "type": "scenario",
                    "entity_type": "scenario",
                    "id": "Opening Scene",
                    "name": "Opening Scene",
                }
            ],
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
    assert hierarchy["entities"] == []


def test_build_campaign_validation_hierarchy_attaches_only_referenced_scenarios():
    campaign = {
        "id": "c1",
        "Name": "Dragonfall",
        "Arcs": {
            "arcs": [
                {"name": "Opening Arc", "scenarios": ["s1", "Missing Scene"]},
                {"name": "Finale", "scenarios": ["Boss Fight"]},
                {"name": "Downtime", "scenarios": []},
            ]
        },
    }

    hierarchy = build_campaign_validation_hierarchy(
        {
            "campaigns": FakeWrapper([campaign]),
            "scenarios": FakeWrapper(
                [
                    {"id": "s1", "Title": "Opening Scene", "NPCs": ["Asha"]},
                    {"id": "boss", "Title": "Boss Fight"},
                    {"id": "unused", "Title": "Unrelated Scene"},
                ]
            ),
        },
        campaign,
    )

    opening_arc, finale_arc, downtime_arc = hierarchy["arcs"]
    assert opening_arc["scenario_refs"] == ["Missing Scene"]
    assert [scenario["id"] for scenario in opening_arc["scenarios"]] == ["s1"]
    assert opening_arc["scenarios"][0]["npc_refs"] == ["Asha"]
    assert "NPCs" not in opening_arc["scenarios"][0]
    assert finale_arc["scenario_refs"] == []
    assert [scenario["id"] for scenario in finale_arc["scenarios"]] == ["boss"]
    assert downtime_arc["scenario_refs"] == []
    assert "scenarios" not in downtime_arc
    assert hierarchy["entities"] == []


def test_scenario_linked_entity_rules_are_discovered_from_template_metadata():
    rules = discover_scenario_linked_entity_rules(
        {"relics": FakeWrapper([]), "npcs": FakeWrapper([])},
        template_loader=lambda _entity: {
            "fields": [
                {"name": "Scenes", "type": "list_longtext"},
                {"name": "Relics", "type": "list", "linked_type": "Relics"},
                {"name": "Witnesses", "type": "list_longtext", "linked_type": "NPCs"},
                {"name": "IgnoredText", "type": "text", "linked_type": "NPCs"},
            ]
        },
        entity_definitions_loader=lambda: {
            "relics": {"label": "Relics"},
            "npcs": {"label": "NPCs"},
        },
    )

    assert [
        (
            rule.source_field,
            rule.entity_slug,
            rule.expected_type,
            rule.canonical_field,
            rule.child_collection,
        )
        for rule in rules
    ] == [
        ("Relics", "relics", "relic", "relic_refs", "relics"),
        ("Witnesses", "npcs", "npc", "npc_refs", "npcs"),
    ]


def test_build_campaign_validation_hierarchy_attaches_scenario_linked_entities():
    campaign = {
        "id": "c1",
        "Name": "Dragonfall",
        "Arcs": {"arcs": [{"name": "Opening Arc", "scenarios": ["s1"]}]},
    }

    hierarchy = build_campaign_validation_hierarchy(
        {
            "campaigns": FakeWrapper([campaign]),
            "scenarios": FakeWrapper(
                [
                    {
                        "id": "s1",
                        "Title": "Opening Scene",
                        "Creatures": ["Android rebelle"],
                        "NPCs": ["Asha"],
                        "Places": ["Dock Nine"],
                        "Maps": ["Dock Map"],
                    }
                ]
            ),
            "creatures": FakeWrapper([{"Name": "Android rebelle"}]),
            "npcs": FakeWrapper([{"Name": "Asha"}]),
            "places": FakeWrapper([{"Name": "Dock Nine"}]),
            "maps": FakeWrapper([{"Name": "Dock Map"}]),
        },
        campaign,
    )
    graph = validate_reference_graph(hierarchy, campaign=campaign)

    scenario = hierarchy["arcs"][0]["scenarios"][0]
    assert "creature_refs" not in scenario
    assert "npc_refs" not in scenario
    assert "location_refs" not in scenario
    assert "map_refs" not in scenario
    assert [creature["id"] for creature in scenario["creatures"]] == [
        "Android rebelle"
    ]
    assert [npc["id"] for npc in scenario["npcs"]] == ["Asha"]
    assert [place["id"] for place in scenario["locations"]] == ["Dock Nine"]
    assert [map_item["id"] for map_item in scenario["maps"]] == ["Dock Map"]
    assert hierarchy["entities"] == []
    assert graph.issues == ()


def test_missing_scenario_linked_entity_refs_remain_missing_references():
    campaign = {
        "id": "c1",
        "Name": "Dragonfall",
        "Arcs": {"arcs": [{"name": "Opening Arc", "scenarios": ["s1"]}]},
    }

    hierarchy = build_campaign_validation_hierarchy(
        {
            "campaigns": FakeWrapper([campaign]),
            "scenarios": FakeWrapper(
                [{"id": "s1", "Title": "Opening Scene", "Creatures": ["Missing Bot"]}]
            ),
            "creatures": FakeWrapper([]),
        },
        campaign,
    )
    graph = validate_reference_graph(hierarchy, campaign=campaign)

    scenario = hierarchy["arcs"][0]["scenarios"][0]
    assert scenario["creature_refs"] == ["Missing Bot"]
    assert [issue.issue_type for issue in graph.issues] == [
        IssueType.MISSING_REFERENCE
    ]
    assert graph.issues[0].payload.field == "creature_refs"
    assert graph.issues[0].payload.referenced_name == "Missing Bot"


def test_custom_scenario_linked_entity_field_uses_template_derived_rules():
    campaign = {
        "id": "c1",
        "Name": "Dragonfall",
        "Arcs": {"arcs": [{"name": "Opening Arc", "scenarios": ["s1"]}]},
    }
    rules = discover_scenario_linked_entity_rules(
        {"relics": FakeWrapper([])},
        template_loader=lambda _entity: {
            "fields": [
                {"name": "Relics", "type": "list", "linked_type": "Relics"},
                {"name": "BackupRelics", "type": "list", "linked_type": "Relics"},
            ]
        },
        entity_definitions_loader=lambda: {"relics": {"label": "Relics"}},
    )

    hierarchy = build_campaign_validation_hierarchy(
        {
            "campaigns": FakeWrapper([campaign]),
            "scenarios": FakeWrapper(
                [
                    {
                        "id": "s1",
                        "Title": "Opening Scene",
                        "Relics": ["Sun Spear"],
                        "BackupRelics": ["Moon Shield"],
                    }
                ]
            ),
            "relics": FakeWrapper([{"Name": "Sun Spear"}, {"Name": "Moon Shield"}]),
        },
        campaign,
        scenario_link_rules=rules,
    )
    graph = validate_reference_graph(
        hierarchy,
        campaign=campaign,
        config=campaign_validation_reference_config(rules),
    )

    scenario = hierarchy["arcs"][0]["scenarios"][0]
    assert "scenario.Relics" not in FIELD_EXPECTED_TYPES
    assert "relic_refs" not in scenario
    assert [relic["id"] for relic in scenario["relics"]] == [
        "Sun Spear",
        "Moon Shield",
    ]
    assert hierarchy["entities"] == []
    assert graph.issues == ()


def test_build_campaign_validation_hierarchy_resolves_arc_scenario_refs_by_key_fields():
    campaign = {
        "id": "c1",
        "Name": "Dragonfall",
        "Arcs": {
            "arcs": [
                {
                    "name": "Keyed Arc",
                    "scenarios": [
                        "scenario-key",
                        {"slug": "scenario-slug"},
                        {"title": "Lower Title"},
                        {"Title": "Missing Scene"},
                    ],
                }
            ]
        },
    }

    hierarchy = build_campaign_validation_hierarchy(
        {
            "campaigns": FakeWrapper([campaign]),
            "scenarios": FakeWrapper(
                [
                    {"key": "scenario-key", "Title": "Key Match"},
                    {"slug": "scenario-slug", "Title": "Slug Match"},
                    {"title": "Lower Title"},
                ]
            ),
        },
        campaign,
    )

    arc = hierarchy["arcs"][0]

    assert [scenario["id"] for scenario in arc["scenarios"]] == [
        "scenario-key",
        "scenario-slug",
        "Lower Title",
    ]
    assert arc["scenario_refs"] == ["Missing Scene"]
    assert hierarchy["entities"] == []


def test_attached_arc_scenarios_are_not_duplicated_in_flat_entity_catalog():
    campaign = {
        "id": "c1",
        "Name": "Dragonfall",
        "Arcs": {"arcs": [{"name": "Opening Arc", "scenarios": ["s1"]}]},
    }

    hierarchy = build_campaign_validation_hierarchy(
        {
            "campaigns": FakeWrapper([campaign]),
            "scenarios": FakeWrapper([{"id": "s1", "Title": "Opening Scene"}]),
        },
        campaign,
    )
    graph = validate_reference_graph(hierarchy, campaign=campaign)

    assert [entity.identifier for entity in graph.entities] == [
        "c1",
        "Opening Arc",
        "s1",
    ]
    assert hierarchy["entities"] == []
    assert graph.issues == ()


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


def test_launcher_hierarchy_prompt_yes_skips_issue_and_shows_summary(monkeypatch):
    prompts = []
    summaries = []

    def answer_yes(title, message):
        prompts.append((title, message))
        return True

    monkeypatch.setattr("tkinter.messagebox.askyesno", answer_yes)
    monkeypatch.setattr(
        "src.ui.validation.campaign_validation_launcher.open_validation_summary_dialog",
        lambda _master, summary: summaries.append(summary),
    )

    launcher = CampaignHierarchyValidationLauncher(FakeApp({}))
    run = _invalid_hierarchy_run()

    launcher._handle_step(run, run.first_step)

    assert prompts == [
        (
            "Hierarchy consistency",
            (
                'Location "Sibling Place" is attached under Arc "A2", not '
                'Arc "A1", in the validation hierarchy.\n\n'
                "Ignore this issue for this session and continue validation?\n\n"
                "Choose Yes to ignore it now. Choose No to open resolution options."
            ),
        )
    ]
    assert summaries == [run.controller.summary]
    assert summaries[0].completed is True
    assert summaries[0].skipped_session == 1
    assert summaries[0].canceled is False


def test_launcher_hierarchy_prompt_no_opens_resolution_dialog(monkeypatch):
    prompts = []
    summaries = []
    opened_dialogs = []

    def answer_no(title, message):
        prompts.append((title, message))
        return False

    def open_dialog(master, controller, step, **kwargs):
        opened_dialogs.append((master, controller, step, kwargs))
        return object()

    monkeypatch.setattr("tkinter.messagebox.askyesno", answer_no)
    monkeypatch.setattr(
        "src.ui.validation.campaign_validation_launcher.open_validation_summary_dialog",
        lambda _master, summary, **_kwargs: summaries.append(summary),
    )
    monkeypatch.setattr(
        "src.ui.validation.campaign_validation_launcher.open_invalid_hierarchy_dialog",
        open_dialog,
    )

    launcher = CampaignHierarchyValidationLauncher(FakeApp({}))
    run = _invalid_hierarchy_run()

    launcher._handle_step(run, run.first_step)

    assert len(prompts) == 1
    assert summaries == []
    assert len(opened_dialogs) == 1
    master, controller, step, kwargs = opened_dialogs[0]
    assert master is launcher.app
    assert controller is run.controller
    assert step is run.first_step
    assert kwargs["reference"] is not None
    assert kwargs["target"] is not None
    assert kwargs["config"].on_step is not None
    assert run.controller.summary.completed is True
    assert run.controller.summary.canceled is False
    assert run.controller.summary.skipped_session == 0
    assert run.controller.summary.resolved == 0
    assert run.controller.current_issue == run.first_step.issue


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
    assert summary.metrics.entities_visited == len(run.graph.entities) == 3
    assert summary.metrics.references_checked == len(run.graph.references) == 1
    assert summary.metrics.elapsed_seconds >= 0
    assert any(run.graph.debug_summary in message for message in log_messages)
    assert any(
        "entities_visited=3" in message and "references_checked=1" in message
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

    assert "Scanning arcs..." in phases
    assert "Scanning scenarios..." in phases
