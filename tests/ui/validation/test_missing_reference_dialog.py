"""Regression tests for missing-reference validation dialog helpers."""

from src.ui.validation import (
    ValidationWizardController,
    ValidationWizardIssue,
    ValidationWizardStatus,
    resolve_reference_for_issue,
)
from src.ui.validation.dialogs import (
    GenericEditorLauncher,
    MissingReferenceDialog,
    MissingReferenceDialogConfig,
    build_prefilled_entity,
    creation_request_from_issue,
    entity_slug_for_expected_type,
)
from src.validation import validate_reference_graph


def _wizard_for(hierarchy):
    graph = validate_reference_graph(hierarchy)
    reference = resolve_reference_for_issue(graph.issues[0], graph.references)
    controller = ValidationWizardController(
        [ValidationWizardIssue(issue=graph.issues[0], reference=reference)]
    )
    controller.start()
    return graph, reference, controller


class _SavedEditor:
    def __init__(self, item):
        self.item = item
        self.saved = True


class _Wrapper:
    def __init__(self, slug):
        self.entity_type = slug
        self.saved_items = []

    def save_item(self, item, **kwargs):
        self.saved_items.append(dict(item))


def test_entity_slug_for_expected_type_maps_validator_types_to_generic_slugs():
    assert entity_slug_for_expected_type("scenario") == "scenarios"
    assert entity_slug_for_expected_type("npc") == "npcs"
    assert entity_slug_for_expected_type("location") == "places"
    assert entity_slug_for_expected_type("arc") == "arcs"


def test_build_prefilled_entity_sets_referenced_name_parent_and_metadata():
    request = creation_request_from_issue(
        validate_reference_graph(
            {"type": "arc", "id": "A1", "scenario_refs": ["Missing Scenario"]}
        ).issues[0]
    )
    template = {
        "fields": [
            {"name": "Title", "type": "text"},
            {"name": "Parent", "type": "text"},
            {"name": "type", "type": "text"},
        ]
    }

    entity = build_prefilled_entity(template, request)

    assert entity["Title"] == "Missing Scenario"
    assert entity["Parent"] == "A1"
    assert entity["type"] == "scenario"
    assert entity["__validation_parent"] == "A1"
    assert entity["__validation_expected_type"] == "scenario"


def test_generic_editor_launcher_returns_saved_entity_and_persists_it():
    wrappers = {}

    def wrapper_factory(slug):
        wrapper = _Wrapper(slug)
        wrappers[slug] = wrapper
        return wrapper

    def editor_factory(master, item, template, wrapper, creation_mode=False):
        assert creation_mode is True
        item["Name"] = f"{item['Name']} Saved"
        return _SavedEditor(item)

    launcher = GenericEditorLauncher(
        editor_factory=editor_factory,
        template_loader=lambda slug: {"fields": [{"name": "Name", "type": "text"}]},
        wrapper_factory=wrapper_factory,
        wait_for_editor=False,
    )
    graph = validate_reference_graph(
        {"type": "campaign", "id": "C1", "arc_refs": ["Missing Arc"]}
    )
    request = creation_request_from_issue(graph.issues[0])

    result = launcher.create_entity(None, request)

    assert result is not None
    assert result.entity_slug == "arcs"
    assert result.entity["Name"] == "Missing Arc Saved"
    assert wrappers["arcs"].saved_items == [result.entity]


def test_dialog_create_opens_generic_editor_and_returns_entity_to_controller():
    hierarchy = {"type": "arc", "id": "A1", "scenario_refs": ["Missing Scenario"]}
    graph, reference, controller = _wizard_for(hierarchy)
    observed_steps = []

    def editor_factory(master, item, template, wrapper, creation_mode=False):
        item["id"] = "S1"
        item["type"] = "scenario"
        return _SavedEditor(item)

    launcher = GenericEditorLauncher(
        editor_factory=editor_factory,
        template_loader=lambda slug: {
            "fields": [
                {"name": "Name", "type": "text"},
                {"name": "Parent", "type": "text"},
            ]
        },
        wrapper_factory=_Wrapper,
        wait_for_editor=False,
    )
    dialog = MissingReferenceDialog(
        None,
        controller,
        graph.issues[0],
        reference=reference,
        config=MissingReferenceDialogConfig(
            generic_editor_launcher=launcher,
            on_step=observed_steps.append,
        ),
    )

    step = dialog.create_via_generic_editor()

    assert step.status == ValidationWizardStatus.COMPLETED
    assert hierarchy["scenario_refs"] == ["S1"]
    assert hierarchy["scenarios"] == [dialog.last_created_entity]
    assert dialog.last_created_entity["Name"] == "Missing Scenario"
    assert dialog.last_created_entity["Parent"] == "A1"
    assert [observed.status for observed in observed_steps] == [
        ValidationWizardStatus.AWAITING_ENTITY_CREATION,
        ValidationWizardStatus.COMPLETED,
    ]


def test_dialog_actions_delegate_remap_remove_and_ignore_to_controller():
    remap_hierarchy = {
        "type": "campaign",
        "id": "C1",
        "arc_refs": ["Missing Arc"],
        "arcs": [{"type": "arc", "id": "A1", "name": "Arc One"}],
    }
    graph, reference, controller = _wizard_for(remap_hierarchy)
    dialog = MissingReferenceDialog(
        None,
        controller,
        graph.issues[0],
        reference=reference,
        config=MissingReferenceDialogConfig(remap_target_provider=lambda issue: "A1"),
    )

    assert dialog.remap().status == ValidationWizardStatus.COMPLETED
    assert remap_hierarchy["arc_refs"] == ["A1"]

    remove_hierarchy = {"type": "campaign", "id": "C1", "arc_refs": ["Missing Arc"]}
    graph, reference, controller = _wizard_for(remove_hierarchy)
    dialog = MissingReferenceDialog(None, controller, graph.issues[0], reference=reference)

    assert dialog.remove_reference().status == ValidationWizardStatus.COMPLETED
    assert remove_hierarchy["arc_refs"] == []

    ignore_hierarchy = {"type": "campaign", "id": "C1", "arc_refs": ["Missing Arc"]}
    graph, reference, controller = _wizard_for(ignore_hierarchy)
    dialog = MissingReferenceDialog(None, controller, graph.issues[0], reference=reference)

    assert dialog.ignore().status == ValidationWizardStatus.COMPLETED
    assert controller.summary.skipped_session == 1
    assert ignore_hierarchy["arc_refs"] == ["Missing Arc"]
