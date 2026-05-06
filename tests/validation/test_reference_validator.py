"""Regression tests for deterministic reference validation."""

from src.validation import IssueType, validate_reference_graph, validate_references


def _sample_hierarchy():
    return {
        "type": "campaign",
        "id": "C1",
        "name": "Campaign One",
        "arc_refs": ["A1", "Missing Arc"],
        "arcs": [
            {
                "type": "arc",
                "id": "A1",
                "name": "Arc One",
                "scenario_refs": [
                    {"ref": "S1", "type": "location"},
                    "S2",
                ],
                "scenarios": [
                    {"type": "scenario", "id": "S1", "name": "Scenario One"},
                ],
            },
            {
                "type": "arc",
                "id": "A2",
                "name": "Arc Two",
                "scenarios": [
                    {"type": "scenario", "id": "S2", "name": "Scenario Two"},
                ],
            },
        ],
    }


def test_validate_references_reports_missing_type_and_hierarchy_in_traversal_order():
    """Verify missing, typed and misplaced references are reported deterministically."""
    issues = validate_references(_sample_hierarchy(), campaign={"id": "sample"})

    assert [issue.issue_type for issue in issues] == [
        IssueType.MISSING_REFERENCE,
        IssueType.INVALID_REFERENCE_TYPE,
        IssueType.INVALID_HIERARCHY,
    ]
    assert [issue.payload.referenced_name for issue in issues] == ["Missing Arc", "S1", "S2"]
    assert issues[1].payload.expected_type == "scenario"
    assert issues[1].payload.actual_type == "location"
    assert issues[2].payload.source_entity == "A1"
    assert issues[2].payload.target_path[-1] == "scenario:S2"
    assert issues[2].payload.resolution_hint


def test_validate_reference_graph_exposes_entities_and_references_for_interactive_resolution():
    """Verify traversal metadata is available to interactive resolution UIs."""
    result = validate_reference_graph(_sample_hierarchy(), campaign={"id": "sample"})

    assert [entity.identifier for entity in result.entities] == ["C1", "A1", "S1", "A2", "S2"]
    assert [reference.reference_value for reference in result.references] == ["A1", "Missing Arc", "S1", "S2"]
    assert result.references[0].path == ("campaign:C1", "arc_refs", "[0]")


def test_validate_references_returns_empty_list_for_valid_direct_children():
    """Verify valid references to direct children are accepted."""
    hierarchy = {
        "type": "campaign",
        "id": "C1",
        "arc_refs": ["A1"],
        "arcs": [
            {
                "type": "arc",
                "id": "A1",
                "scenario_refs": ["S1"],
                "scenarios": [{"type": "scenario", "id": "S1"}],
            }
        ],
    }

    assert validate_references(hierarchy, campaign={"id": "sample"}) == []
