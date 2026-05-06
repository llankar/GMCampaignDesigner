"""Tests for INVALID_HIERARCHY wizard messages."""

from src.ui.validation import ValidationWizardController, ValidationWizardIssue
from src.ui.validation.messages import format_hierarchy_issue_message
from src.validation import (
    IssuePayload,
    IssueType,
    ValidationIssue,
    validate_reference_graph,
)


def _hierarchy_issue(**payload_overrides) -> ValidationIssue:
    payload = {
        "source_entity": "This is the end",
        "field": "scenario_refs",
        "referenced_name": "Missing Finale",
        "expected_type": "scenario",
        "source_type": "arc",
        "hierarchy_path": ("campaign:C1", "arc:This is the end", "scenario_refs", "[0]"),
        "source_path": ("campaign:C1", "arc:This is the end"),
    }
    payload.update(payload_overrides)
    return ValidationIssue(
        issue_type=IssueType.INVALID_HIERARCHY,
        payload=IssuePayload(**payload),
    )


def test_hierarchy_message_distinguishes_missing_target() -> None:
    issue = _hierarchy_issue()

    assert format_hierarchy_issue_message(issue) == (
        'Scenario "Missing Finale" is not present under Arc "This is the end" '
        "in the validation hierarchy."
    )


def test_hierarchy_message_distinguishes_global_target_not_under_expected_parent() -> None:
    issue = _hierarchy_issue(
        referenced_name="Final Scene",
        target_path=("campaign:C1", "entities", "[0]", "scenario:S-final"),
    )

    assert format_hierarchy_issue_message(issue) == (
        'Scenario "Final Scene" exists, but it is not attached under '
        'Arc "This is the end" in the validation hierarchy.'
    )


def test_hierarchy_message_distinguishes_target_under_another_parent() -> None:
    issue = _hierarchy_issue(
        referenced_name="Final Scene",
        target_path=(
            "campaign:C1",
            "arcs",
            "[1]",
            "arc:Sibling Arc",
            "scenarios",
            "[0]",
            "scenario:S-final",
        ),
    )

    assert format_hierarchy_issue_message(issue) == (
        'Scenario "Final Scene" is attached under Arc "Sibling Arc", not '
        'Arc "This is the end", in the validation hierarchy.'
    )


def test_wizard_step_uses_specific_hierarchy_message() -> None:
    hierarchy = {
        "type": "campaign",
        "id": "C1",
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
        tuple(ValidationWizardIssue(issue=issue) for issue in graph.issues),
        campaign=graph.campaign,
    )

    step = controller.start()

    assert step.issue is not None
    assert step.issue.issue_type == IssueType.INVALID_HIERARCHY
    assert step.message == (
        'Location "Sibling Place" is attached under Arc "A2", not Arc "A1", '
        "in the validation hierarchy."
    )
