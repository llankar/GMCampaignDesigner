"""Minimal campaign hierarchy covering the validation wizard decision matrix."""

from __future__ import annotations

from typing import Any

from src.ui.validation import (
    ValidationWizardController,
    ValidationWizardIssue,
    resolve_reference_for_issue,
)
from src.validation import IssueType, ReferenceValidationResult, validate_reference_graph

EXPECTED_ISSUE_SEQUENCE = (
    (IssueType.MISSING_REFERENCE, "Arc To Remove"),
    (IssueType.AMBIGUOUS_REFERENCE, "Shared Place"),
    (IssueType.INVALID_HIERARCHY, "Sibling Scenario"),
    (IssueType.MISSING_REFERENCE, "Scenario To Create"),
    (IssueType.MISSING_REFERENCE, "Scenario To Ignore"),
)

EXPECTED_DECISION_SUMMARY = {
    "total_issues": 5,
    "resolved": 4,
    "skipped_session": 1,
    "changes_applied": (
        "C1.arc_refs: référence supprimée",
        "A1.location_refs: Shared Place → L2",
        "A1.scenario_refs: Sibling Scenario → S-valid",
        "scenarios: entité ajoutée",
        "A1.scenario_refs: Scenario To Create → S-created",
    ),
    "messages": (
        "Référence « Arc To Remove » supprimée.",
        "Référence remappée vers « L2 ».",
        "Référence remappée vers « S-valid ».",
        "Nouvelle entité « S-created » reliée.",
        "Issue ignorée pour cette session : Scenario To Ignore",
    ),
}


def build_minimal_validation_hierarchy() -> dict[str, Any]:
    """Return a tiny mutable campaign graph with all wizard issue classes."""

    return {
        "type": "campaign",
        "id": "C1",
        "name": "Minimal Validation Campaign",
        "arc_refs": ["Arc To Remove"],
        "arcs": [
            {
                "type": "arc",
                "id": "A1",
                "name": "Main Arc",
                "location_refs": ["Shared Place"],
                "scenario_refs": [
                    "Sibling Scenario",
                    "Scenario To Create",
                    "Scenario To Ignore",
                ],
                "locations": [
                    {"type": "location", "id": "L1", "name": "Shared Place"},
                    {"type": "location", "id": "L2", "name": "Shared Place"},
                ],
                "scenarios": [
                    {"type": "scenario", "id": "S-valid", "name": "Valid Scenario"},
                ],
            },
            {
                "type": "arc",
                "id": "A2",
                "name": "Sibling Arc",
                "scenarios": [
                    {
                        "type": "scenario",
                        "id": "S-sibling",
                        "name": "Sibling Scenario",
                    }
                ],
            },
        ],
    }


def build_minimal_validation_wizard(
    hierarchy: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], ReferenceValidationResult, ValidationWizardController]:
    """Build the graph and controller bound to the minimal hierarchy."""

    campaign_hierarchy = (
        hierarchy if hierarchy is not None else build_minimal_validation_hierarchy()
    )
    graph = validate_reference_graph(campaign_hierarchy)
    controller = ValidationWizardController(
        tuple(
            ValidationWizardIssue(
                issue=issue,
                reference=resolve_reference_for_issue(issue, graph.references),
            )
            for issue in graph.issues
        ),
        reference_resolver=lambda issue: resolve_reference_for_issue(
            issue, graph.references
        ),
    )
    return campaign_hierarchy, graph, controller
