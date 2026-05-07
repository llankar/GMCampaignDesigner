"""Regression tests for invalid-hierarchy validation dialog helpers."""

from src.ui.validation import (
    ValidationWizardController,
    ValidationWizardIssue,
    ValidationWizardStatus,
    resolve_reference_for_issue,
    resolve_target_for_issue,
)
from src.ui.validation.dialogs import (
    InvalidHierarchyDialog,
    InvalidHierarchyDialogConfig,
)
from src.ui.validation.labels import (
    ATTACH_LABEL,
    IGNORE_LABEL,
    REMAP_LABEL,
    REMOVE_LABEL,
    STOP_VALIDATION_LABEL,
)
from src.validation import IssueType, ReferenceValidatorConfig, validate_reference_graph


def _invalid_hierarchy_wizard():
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
                "locations": [
                    {"type": "location", "id": "L1", "name": "Local Place"}
                ],
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
    graph = validate_reference_graph(hierarchy, campaign={"id": "sample"})
    reference = resolve_reference_for_issue(graph.issues[0], graph.references)
    target = resolve_target_for_issue(graph.issues[0], graph.entities)
    controller = ValidationWizardController(
        [
            ValidationWizardIssue(
                issue=graph.issues[0],
                reference=reference,
                target=target,
            )
        ],
        campaign=graph.campaign,
    )
    step = controller.start()

    assert step.issue is not None
    assert step.issue.issue_type == IssueType.INVALID_HIERARCHY

    return hierarchy, graph, reference, target, controller, step


def _unsupported_attach_wizard():
    hierarchy = {
        "type": "campaign",
        "id": "C1",
        "arcs": [
            {
                "type": "arc",
                "id": "A1",
                "scenarios": [
                    {
                        "type": "scenario",
                        "id": "S1",
                        "custom_refs": ["C1"],
                    }
                ],
            }
        ],
        "entities": [{"type": "custom", "id": "C1"}],
    }
    graph = validate_reference_graph(
        hierarchy,
        campaign={"id": "sample"},
        config=ReferenceValidatorConfig(
            field_expected_types={"scenario.custom_refs": "custom"}
        ),
    )
    reference = resolve_reference_for_issue(graph.issues[0], graph.references)
    target = resolve_target_for_issue(graph.issues[0], graph.entities)
    controller = ValidationWizardController(
        [
            ValidationWizardIssue(
                issue=graph.issues[0],
                reference=reference,
                target=target,
            )
        ],
        campaign=graph.campaign,
    )
    step = controller.start()

    assert step.issue is not None
    assert step.issue.issue_type == IssueType.INVALID_HIERARCHY

    return hierarchy, graph, reference, target, controller, step


def _scenario_creature_wizard():
    hierarchy = {
        "type": "campaign",
        "id": "C1",
        "arcs": [
            {
                "type": "arc",
                "id": "A1",
                "scenarios": [
                    {
                        "type": "scenario",
                        "id": "S1",
                        "name": "Anthony Steel",
                        "creature_refs": ["Android rebelle"],
                    }
                ],
            }
        ],
        "entities": [
            {"type": "creature", "id": "C-android", "name": "Android rebelle"}
        ],
    }
    graph = validate_reference_graph(hierarchy, campaign={"id": "sample"})
    reference = resolve_reference_for_issue(graph.issues[0], graph.references)
    target = resolve_target_for_issue(graph.issues[0], graph.entities)
    controller = ValidationWizardController(
        [
            ValidationWizardIssue(
                issue=graph.issues[0],
                reference=reference,
                target=target,
            )
        ],
        campaign=graph.campaign,
    )
    step = controller.start()

    assert step.issue is not None
    assert step.issue.issue_type == IssueType.INVALID_HIERARCHY

    return hierarchy, graph, reference, target, controller, step


def test_dialog_ignore_skips_invalid_hierarchy_issue_for_session():
    hierarchy, graph, reference, target, controller, step = _invalid_hierarchy_wizard()
    observed_steps = []
    dialog = InvalidHierarchyDialog(
        None,
        controller,
        step,
        reference=reference,
        target=target,
        config=InvalidHierarchyDialogConfig(on_step=observed_steps.append),
    )

    next_step = dialog.ignore()

    assert next_step.status == ValidationWizardStatus.COMPLETED
    assert observed_steps == [next_step]
    assert controller.summary.skipped_session == 1
    assert controller.summary.resolved == 0
    assert hierarchy["arcs"][0]["location_refs"] == ["Sibling Place"]
    assert graph.issues == (step.issue,)


def test_dialog_remove_deletes_invalid_hierarchy_reference():
    hierarchy, _graph, reference, target, controller, step = _invalid_hierarchy_wizard()
    dialog = InvalidHierarchyDialog(
        None, controller, step, reference=reference, target=target
    )

    next_step = dialog.remove_reference()

    assert next_step.status == ValidationWizardStatus.COMPLETED
    assert controller.summary.resolved == 1
    assert controller.summary.skipped_session == 0
    assert hierarchy["arcs"][0]["location_refs"] == []


def test_dialog_attach_moves_existing_target_under_source_and_advances():
    hierarchy, _graph, reference, target, controller, step = _invalid_hierarchy_wizard()
    dialog = InvalidHierarchyDialog(
        None, controller, step, reference=reference, target=target
    )

    next_step = dialog.attach()

    assert next_step.status == ValidationWizardStatus.COMPLETED
    assert controller.summary.resolved == 1
    assert controller.summary.skipped_session == 0
    assert hierarchy["arcs"][0]["location_refs"] == ["Sibling Place"]
    assert [location["id"] for location in hierarchy["arcs"][0]["locations"]] == [
        "L1",
        "L2",
    ]
    assert hierarchy["arcs"][1]["locations"] == []
    assert validate_reference_graph(hierarchy, campaign={"id": "sample"}).issues == ()


def test_dialog_attach_supports_scenario_creature_reference():
    hierarchy, _graph, reference, target, controller, step = _scenario_creature_wizard()
    dialog = InvalidHierarchyDialog(
        None, controller, step, reference=reference, target=target
    )

    assert dialog.available_action_labels[0] == ATTACH_LABEL

    next_step = dialog.attach()

    assert next_step.status == ValidationWizardStatus.COMPLETED
    scenario = hierarchy["arcs"][0]["scenarios"][0]
    assert scenario["creature_refs"] == ["Android rebelle"]
    assert scenario["creatures"] == [
        {"type": "creature", "id": "C-android", "name": "Android rebelle"}
    ]
    assert hierarchy["entities"] == []
    assert validate_reference_graph(hierarchy, campaign={"id": "sample"}).issues == ()


def test_dialog_remap_uses_configured_target_provider():
    hierarchy, _graph, reference, target, controller, step = _invalid_hierarchy_wizard()
    dialog = InvalidHierarchyDialog(
        None,
        controller,
        step,
        reference=reference,
        target=target,
        config=InvalidHierarchyDialogConfig(
            remap_target_provider=lambda issue: "L1",
        ),
    )

    next_step = dialog.remap()

    assert next_step is not None
    assert next_step.status == ValidationWizardStatus.COMPLETED
    assert controller.summary.resolved == 1
    assert hierarchy["arcs"][0]["location_refs"] == ["L1"]


def test_dialog_advertises_remap_only_when_target_provider_exists():
    _hierarchy, _graph, reference, target, controller, step = _invalid_hierarchy_wizard()
    dialog = InvalidHierarchyDialog(
        None, controller, step, reference=reference, target=target
    )

    assert dialog.available_action_labels == (
        ATTACH_LABEL,
        REMOVE_LABEL,
        IGNORE_LABEL,
        STOP_VALIDATION_LABEL,
    )
    assert "remap" not in dialog._message_text().lower()

    remap_dialog = InvalidHierarchyDialog(
        None,
        controller,
        step,
        reference=reference,
        target=target,
        config=InvalidHierarchyDialogConfig(remap_target_provider=lambda _issue: "L1"),
    )

    assert remap_dialog.available_action_labels == (
        ATTACH_LABEL,
        REMAP_LABEL,
        REMOVE_LABEL,
        IGNORE_LABEL,
        STOP_VALIDATION_LABEL,
    )
    assert "remap" in remap_dialog._message_text().lower()


def test_dialog_hides_attach_when_target_cannot_be_safely_placed():
    _hierarchy, _graph, reference, target, controller, step = (
        _unsupported_attach_wizard()
    )
    dialog = InvalidHierarchyDialog(
        None, controller, step, reference=reference, target=target
    )

    assert dialog.available_action_labels == (
        REMOVE_LABEL,
        IGNORE_LABEL,
        STOP_VALIDATION_LABEL,
    )
    assert "attach the existing target" not in dialog._message_text().lower()


def test_dialog_remap_without_target_provider_reports_error_without_advancing():
    _hierarchy, _graph, reference, target, controller, step = (
        _invalid_hierarchy_wizard()
    )
    errors = []
    dialog = InvalidHierarchyDialog(
        None,
        controller,
        step,
        reference=reference,
        target=target,
        config=InvalidHierarchyDialogConfig(on_error=errors.append),
    )

    next_step = dialog.remap()

    assert next_step is None
    assert errors == ["No hierarchy target selector is configured for remapping."]
    assert controller.current_issue == step.issue
    assert controller.summary.resolved == 0
    assert controller.summary.skipped_session == 0


def test_dialog_stop_validation_is_explicit_cancel_action():
    hierarchy, _graph, reference, target, controller, step = _invalid_hierarchy_wizard()
    dialog = InvalidHierarchyDialog(
        None, controller, step, reference=reference, target=target
    )

    next_step = dialog.stop_validation()

    assert next_step.status == ValidationWizardStatus.CANCELED
    assert next_step.summary is not None
    assert next_step.summary.canceled is True
    assert hierarchy["arcs"][0]["location_refs"] == ["Sibling Place"]
