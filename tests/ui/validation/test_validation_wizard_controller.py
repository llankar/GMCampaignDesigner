"""Regression tests for the validation wizard controller workflow."""

from src.services import SessionIgnoreStore
from src.ui.validation import (
    ValidationWizardAction,
    ValidationWizardController,
    ValidationWizardIssue,
    ValidationWizardStatus,
    resolve_reference_for_issue,
)
from src.validation import validate_reference_graph


def _graph_for(hierarchy):
    return validate_reference_graph(hierarchy, campaign={"id": "sample"})


def _wizard_items(graph):
    return tuple(
        ValidationWizardIssue(
            issue=issue,
            reference=resolve_reference_for_issue(issue, graph.references),
        )
        for issue in graph.issues
    )


def test_wizard_starts_on_first_non_ignored_issue_and_finishes_with_summary():
    hierarchy = {
        "type": "campaign",
        "id": "C1",
        "arc_refs": ["Missing One", "Missing Two"],
    }
    graph = _graph_for(hierarchy)
    ignore_store = SessionIgnoreStore()
    ignore_store.ignore(graph.issues[0])
    controller = ValidationWizardController(
        _wizard_items(graph),
        campaign=graph.campaign,
        ignore_store=ignore_store,
    )

    first_step = controller.start()
    assert first_step.status == ValidationWizardStatus.SHOW_ISSUE
    assert first_step.issue == graph.issues[1]
    assert first_step.progress.current_index == 1
    assert first_step.progress.visible_total == 1

    summary_step = controller.submit_action(ValidationWizardAction.REMOVE)
    assert summary_step.status == ValidationWizardStatus.COMPLETED
    assert hierarchy["arc_refs"] == ["Missing One"]
    assert summary_step.summary.resolved == 1
    assert summary_step.summary.skipped_session == 0
    assert summary_step.summary.changes_applied == ("C1.arc_refs: référence supprimée",)


def test_wizard_skip_session_ignores_current_issue_and_advances():
    hierarchy = {
        "type": "campaign",
        "id": "C1",
        "arc_refs": ["Missing One", "Missing Two"],
    }
    graph = _graph_for(hierarchy)
    controller = ValidationWizardController(_wizard_items(graph), campaign=graph.campaign)

    assert controller.start().issue == graph.issues[0]
    next_step = controller.submit_action(ValidationWizardAction.SKIP_SESSION)

    assert next_step.status == ValidationWizardStatus.SHOW_ISSUE
    assert next_step.issue == graph.issues[1]
    assert controller.summary.skipped_session == 1
    assert hierarchy["arc_refs"] == ["Missing One", "Missing Two"]


def test_wizard_cancel_returns_canceled_summary_without_mutating():
    hierarchy = {"type": "campaign", "id": "C1", "arc_refs": ["Missing"]}
    graph = _graph_for(hierarchy)
    controller = ValidationWizardController(_wizard_items(graph), campaign=graph.campaign)

    controller.start()
    step = controller.submit_action(ValidationWizardAction.CANCEL)

    assert step.status == ValidationWizardStatus.CANCELED
    assert step.summary.canceled is True
    assert step.summary.resolved == 0
    assert hierarchy["arc_refs"] == ["Missing"]


def test_wizard_remap_applies_reference_fix_and_advances():
    hierarchy = {
        "type": "campaign",
        "id": "C1",
        "arc_refs": ["Wrong Arc"],
        "arcs": [{"type": "arc", "id": "A1", "name": "Arc One"}],
    }
    graph = _graph_for(hierarchy)
    controller = ValidationWizardController(_wizard_items(graph), campaign=graph.campaign)

    controller.start()
    step = controller.submit_action(ValidationWizardAction.REMAP, target="A1")

    assert step.status == ValidationWizardStatus.COMPLETED
    assert hierarchy["arc_refs"] == ["A1"]
    assert step.summary.resolved == 1
    assert step.summary.messages == ("Référence remappée vers « A1 ».",)


def test_wizard_resumes_after_entity_creation_and_links_created_entity():
    hierarchy = {"type": "campaign", "id": "C1", "arc_refs": ["Missing Arc"]}
    graph = _graph_for(hierarchy)
    controller = ValidationWizardController(_wizard_items(graph), campaign=graph.campaign)

    controller.start()
    paused = controller.submit_action(ValidationWizardAction.CREATE_ENTITY)
    assert paused.status == ValidationWizardStatus.AWAITING_ENTITY_CREATION

    new_entity = {"type": "arc", "id": "A1", "name": "Created Arc"}
    final_step = controller.resume_after_entity_creation(new_entity)

    assert final_step.status == ValidationWizardStatus.COMPLETED
    assert hierarchy["arc_refs"] == ["A1"]
    assert hierarchy["arcs"] == [new_entity]
    assert final_step.summary.resolved == 1
    assert final_step.summary.changes_applied == (
        "arcs: entité ajoutée",
        "C1.arc_refs: Missing Arc → A1",
    )


def test_wizard_can_use_reference_resolver_for_plain_issue_lists():
    hierarchy = {"type": "campaign", "id": "C1", "arc_refs": ["Missing"]}
    graph = _graph_for(hierarchy)
    controller = ValidationWizardController(
        graph.issues,
        campaign=graph.campaign,
        reference_resolver=lambda issue: resolve_reference_for_issue(issue, graph.references),
    )

    controller.start()
    step = controller.submit_action(ValidationWizardAction.REMOVE)

    assert step.status == ValidationWizardStatus.COMPLETED
    assert hierarchy["arc_refs"] == []
