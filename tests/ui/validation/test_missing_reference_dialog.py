"""Regression tests for missing-reference validation dialog helpers."""

import sys
import types

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
from src.ui.validation.campaign_validation_launcher import (
    build_missing_reference_remap_target_provider,
    remap_target_options_for_issue,
)
from src.ui.validation.labels import REMAP_LABEL
from src.validation import validate_reference_graph


def _wizard_for(hierarchy):
    graph = validate_reference_graph(hierarchy, campaign={"id": "sample"})
    reference = resolve_reference_for_issue(graph.issues[0], graph.references)
    controller = ValidationWizardController(
        [ValidationWizardIssue(issue=graph.issues[0], reference=reference)],
        campaign=graph.campaign,
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
            {"type": "arc", "id": "A1", "scenario_refs": ["Missing Scenario"]},
            campaign={"id": "sample"},
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
        {"type": "campaign", "id": "C1", "arc_refs": ["Missing Arc"]},
        campaign={"id": "sample"},
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


def test_remap_target_options_only_include_expected_entity_type():
    hierarchy = {
        "type": "arc",
        "id": "A1",
        "scenario_refs": ["Missing Scenario"],
        "scenarios": [
            {"type": "scenario", "id": "S1", "name": "Existing Scenario"},
        ],
    }
    graph = validate_reference_graph(hierarchy, campaign={"id": "sample"})

    options = remap_target_options_for_issue(graph.issues[0], graph.entities)

    assert [option.entity.identifier for option in options] == ["S1"]
    assert options[0].display_text.startswith("Existing Scenario (S1)")


def test_remap_target_provider_returns_selector_choice():
    hierarchy = {
        "type": "arc",
        "id": "A1",
        "scenario_refs": ["Missing Scenario"],
        "scenarios": [
            {"type": "scenario", "id": "S1", "name": "Existing Scenario"},
        ],
    }
    graph = validate_reference_graph(hierarchy, campaign={"id": "sample"})
    observed_targets = []

    def selector(master, targets):
        observed_targets.extend(targets)
        return targets[0].entity

    provider = build_missing_reference_remap_target_provider(
        object(),
        graph,
        selector=selector,
    )

    assert provider(graph.issues[0]).identifier == "S1"
    assert [target.entity.identifier for target in observed_targets] == ["S1"]


def test_dialog_show_hides_remap_button_without_provider(monkeypatch):
    graph, reference, controller = _wizard_for(
        {"type": "campaign", "id": "C1", "arc_refs": ["Missing Arc"]}
    )
    fake_ctk = _install_fake_customtkinter(monkeypatch)
    dialog = MissingReferenceDialog(None, controller, graph.issues[0], reference=reference)

    dialog.show()

    assert REMAP_LABEL not in fake_ctk.button_texts
    assert fake_ctk.column_indexes[-3:] == [0, 1, 2]


def test_dialog_show_includes_remap_button_with_provider(monkeypatch):
    graph, reference, controller = _wizard_for(
        {"type": "campaign", "id": "C1", "arc_refs": ["Missing Arc"]}
    )
    fake_ctk = _install_fake_customtkinter(monkeypatch)
    dialog = MissingReferenceDialog(
        None,
        controller,
        graph.issues[0],
        reference=reference,
        config=MissingReferenceDialogConfig(remap_target_provider=lambda issue: "A1"),
    )

    dialog.show()

    assert REMAP_LABEL in fake_ctk.button_texts
    assert fake_ctk.column_indexes[-4:] == [0, 1, 2, 3]


def _install_fake_customtkinter(monkeypatch):
    fake_ctk = types.SimpleNamespace(button_texts=[], column_indexes=[])

    class _Widget:
        def __init__(self, *args, **kwargs):
            pass

        def grid(self, *args, **kwargs):
            return None

        def grid_columnconfigure(self, index, **kwargs):
            fake_ctk.column_indexes.append(index)

        def title(self, *args, **kwargs):
            return None

        def transient(self, *args, **kwargs):
            return None

        def grab_set(self, *args, **kwargs):
            return None

        def geometry(self, *args, **kwargs):
            return None

        def destroy(self):
            return None

    class _Button(_Widget):
        def __init__(self, *args, text="", command=None, **kwargs):
            super().__init__(*args, **kwargs)
            fake_ctk.button_texts.append(text)
            self.command = command

    fake_ctk.CTkToplevel = _Widget
    fake_ctk.CTkFrame = _Widget
    fake_ctk.CTkLabel = _Widget
    fake_ctk.CTkButton = _Button
    fake_ctk.CTkFont = lambda *args, **kwargs: None
    monkeypatch.setitem(sys.modules, "customtkinter", fake_ctk)
    return fake_ctk
