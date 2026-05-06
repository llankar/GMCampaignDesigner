"""End-to-end coverage for the minimal validation decision dataset."""

from __future__ import annotations

from dataclasses import dataclass

from src.ui.validation import (
    ValidationWizardAction,
    ValidationWizardStatus,
    ValidationWizardStep,
)
from src.ui.validation.dialogs import (
    AmbiguousReferenceDialog,
    AmbiguousReferenceDialogConfig,
    GenericEditorCreationResult,
    MissingReferenceDialog,
    MissingReferenceDialogConfig,
)
from src.validation import IssueType

from tests.ui.validation.fixtures import (
    EXPECTED_DECISION_SUMMARY,
    EXPECTED_ISSUE_SEQUENCE,
    build_minimal_validation_wizard,
)


@dataclass
class FakeGenericEditorLauncher:
    """Generic Editor test double returning one saved scenario entity."""

    created_entity: dict[str, str]
    requests: list[object]

    def create_entity(self, master, request) -> GenericEditorCreationResult:
        self.requests.append(request)
        return GenericEditorCreationResult(
            entity=self.created_entity, entity_slug="scenarios"
        )


def _assert_problem(
    step: ValidationWizardStep, expected_type: IssueType, expected_name: str
) -> None:
    assert step.status == ValidationWizardStatus.SHOW_ISSUE
    assert step.issue is not None
    assert step.issue.issue_type == expected_type
    assert step.issue.payload.referenced_name == expected_name


def test_minimal_dataset_exposes_all_required_problems_in_order():
    """The fixture is small but still covers all validation issue scenarios."""

    _hierarchy, graph, _controller = build_minimal_validation_wizard()

    assert tuple(
        (issue.issue_type, issue.payload.referenced_name) for issue in graph.issues
    ) == EXPECTED_ISSUE_SEQUENCE
    assert len(graph.issues[1].payload.candidates) == 2
    assert graph.issues[2].issue_type == IssueType.INVALID_HIERARCHY


def test_minimal_dataset_actions_chain_to_next_problem_and_exact_summary():
    """Simulate GM decisions and verify each transition plus final counters/logs."""

    hierarchy, graph, controller = build_minimal_validation_wizard()
    observed_steps = []

    step = controller.start()
    observed_steps.append(step)
    _assert_problem(step, IssueType.MISSING_REFERENCE, "Arc To Remove")

    step = controller.submit_action(ValidationWizardAction.REMOVE)
    observed_steps.append(step)
    _assert_problem(step, IssueType.AMBIGUOUS_REFERENCE, "Shared Place")

    ambiguous_dialog = AmbiguousReferenceDialog(
        None,
        controller,
        step.issue,
        config=AmbiguousReferenceDialogConfig(
            candidates=[
                entity for entity in graph.entities if entity.entity_type == "location"
            ],
            on_step=observed_steps.append,
        ),
    )
    step = ambiguous_dialog.choose_right()
    _assert_problem(step, IssueType.INVALID_HIERARCHY, "Sibling Place")

    step = controller.submit_action(ValidationWizardAction.REMAP, target="L1")
    observed_steps.append(step)
    _assert_problem(step, IssueType.MISSING_REFERENCE, "Scenario To Create")

    generic_editor = FakeGenericEditorLauncher(
        created_entity={
            "type": "scenario",
            "id": "S-created",
            "name": "Scenario To Create",
        },
        requests=[],
    )
    missing_dialog = MissingReferenceDialog(
        None,
        controller,
        step.issue,
        reference=graph.references[3],
        config=MissingReferenceDialogConfig(
            generic_editor_launcher=generic_editor,
            on_step=observed_steps.append,
        ),
    )
    step = missing_dialog.create_via_generic_editor()
    _assert_problem(step, IssueType.MISSING_REFERENCE, "Scenario To Ignore")

    step = controller.submit_action(ValidationWizardAction.SKIP_SESSION)
    observed_steps.append(step)

    assert step.status == ValidationWizardStatus.COMPLETED
    assert step.summary is not None
    assert step.summary.total_issues == EXPECTED_DECISION_SUMMARY["total_issues"]
    assert step.summary.resolved == EXPECTED_DECISION_SUMMARY["resolved"]
    assert step.summary.skipped_session == EXPECTED_DECISION_SUMMARY["skipped_session"]
    assert step.summary.changes_applied == EXPECTED_DECISION_SUMMARY["changes_applied"]
    assert step.summary.messages == EXPECTED_DECISION_SUMMARY["messages"]
    assert hierarchy["arc_refs"] == []
    assert hierarchy["arcs"][0]["location_refs"] == ["L2", "L1"]
    assert hierarchy["arcs"][0]["scenario_refs"] == [
        "Sibling Scenario",
        "S-created",
        "Scenario To Ignore",
    ]
    assert hierarchy["arcs"][0]["scenarios"][-1] == generic_editor.created_entity
    assert generic_editor.requests[0].referenced_name == "Scenario To Create"
    assert [observed.status for observed in observed_steps] == [
        ValidationWizardStatus.SHOW_ISSUE,
        ValidationWizardStatus.SHOW_ISSUE,
        ValidationWizardStatus.SHOW_ISSUE,
        ValidationWizardStatus.SHOW_ISSUE,
        ValidationWizardStatus.AWAITING_ENTITY_CREATION,
        ValidationWizardStatus.SHOW_ISSUE,
        ValidationWizardStatus.COMPLETED,
    ]
