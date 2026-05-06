"""Regression tests for deterministic reference validation."""

from src.validation import (
    FIELD_EXPECTED_TYPES,
    IssueType,
    validate_reference_graph,
    validate_references,
)


def test_field_expected_types_include_real_template_and_ui_fields_with_legacy_aliases():
    """Verify reference rules track persisted model fields while aliases migrate."""
    expected = {
        "campaign.Arcs": "arc",
        "campaign.LinkedScenarios": "scenario",
        "scenario.NPCs": "npc",
        "scenario.Places": "location",
        "scenario.Creatures": "creature",
        "scenario.Factions": "faction",
        "scenario.Objects": "object",
        "scenario.Events": "event",
        "scenario.Books": "book",
        "scenario.Maps": "map",
        "scenario.Bases": "base",
        "scenario.Villains": "villain",
        "scenario.PCs": "pc",
        "campaign.arc_refs": "arc",
        "arc.scenario_refs": "scenario",
        "scenario.npc_refs": "npc",
    }

    for field_path, expected_type in expected.items():
        assert FIELD_EXPECTED_TYPES[field_path] == expected_type


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
                    {
                        "type": "scenario",
                        "id": "S1",
                        "name": "Scenario One",
                        "npc_refs": ["N2"],
                    },
                ],
            },
            {
                "type": "arc",
                "id": "A2",
                "name": "Arc Two",
                "scenarios": [
                    {
                        "type": "scenario",
                        "id": "S2",
                        "name": "Scenario Two",
                        "npcs": [{"type": "npc", "id": "N2"}],
                    },
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
    assert [issue.payload.referenced_name for issue in issues] == [
        "Missing Arc",
        "S1",
        "N2",
    ]
    assert issues[1].payload.expected_type == "scenario"
    assert issues[1].payload.actual_type == "location"
    assert issues[2].payload.source_entity == "S1"
    assert issues[2].payload.target_path[-1] == "npc:N2"
    assert issues[2].payload.resolution_hint


def test_validate_reference_graph_exposes_entities_and_references_for_interactive_resolution():
    """Verify traversal metadata is available to interactive resolution UIs."""
    result = validate_reference_graph(_sample_hierarchy(), campaign={"id": "sample"})

    assert [entity.identifier for entity in result.entities] == [
        "C1",
        "A1",
        "S1",
        "A2",
        "S2",
        "N2",
    ]
    assert [reference.reference_value for reference in result.references] == [
        "A1",
        "Missing Arc",
        "S1",
        "S2",
        "N2",
    ]
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


def test_validate_references_accepts_arc_scenario_refs_to_graph_scenarios():
    """Verify arc scenario_refs can target scenarios already in the selected graph."""
    hierarchy = {
        "type": "campaign",
        "id": "C1",
        "arcs": [
            {
                "type": "arc",
                "id": "A1",
                "scenario_refs": ["S1", "Scenario Two"],
            }
        ],
        "entities": [
            {"type": "scenario", "id": "S1", "name": "Scenario One"},
            {"type": "scenario", "id": "S2", "name": "Scenario Two"},
        ],
    }

    result = validate_reference_graph(hierarchy, campaign={"id": "C1"})

    assert [entity.identifier for entity in result.entities] == [
        "C1",
        "A1",
        "S1",
        "S2",
    ]
    assert [reference.reference_value for reference in result.references] == [
        "S1",
        "Scenario Two",
    ]
    assert result.issues == ()


def test_validate_references_keeps_non_arc_scenario_refs_strict():
    """Verify graph-membership hierarchy relief is limited to arc scenario refs."""
    hierarchy = _sample_hierarchy()

    issues = validate_references(hierarchy, campaign={"id": "sample"})

    assert [issue.issue_type for issue in issues] == [
        IssueType.MISSING_REFERENCE,
        IssueType.INVALID_REFERENCE_TYPE,
        IssueType.INVALID_HIERARCHY,
    ]
    assert issues[-1].payload.referenced_name == "N2"


def test_validate_reference_graph_uses_selected_campaign_root_not_registry_placeholder():
    """Verify global registry siblings are not scanned as selected campaign children."""
    hierarchy = {
        "type": "registry",
        "id": "global",
        "campaigns": [
            {"type": "campaign", "id": "C1", "name": "Selected", "arc_refs": ["A1"]},
        ],
        "arcs": [
            {
                "type": "arc",
                "id": "A1",
                "scenario_refs": ["Global Scenario Should Not Be Visited"],
                "scenarios": [
                    {"type": "scenario", "id": "S1", "name": "Registry Scenario"},
                ],
            }
        ],
    }

    result = validate_reference_graph(hierarchy, campaign={"id": "C1"})

    assert [entity.identifier for entity in result.entities] == ["C1"]
    assert [reference.reference_value for reference in result.references] == ["A1"]
    assert result.diagnostics.visited_campaigns == 1
    assert result.diagnostics.visited_arcs == 0
    assert result.diagnostics.visited_scenarios == 0
    assert result.diagnostics.visited_references == 1
    assert "campaigns=1" in result.debug_summary
    assert "references=1" in result.debug_summary_path[-1]


def test_validate_reference_graph_walks_validator_built_entities_collection():
    """Verify campaign roots descend into flat UI launcher entity collections."""
    hierarchy = {
        "type": "campaign",
        "id": "C1",
        "arc_refs": ["A1"],
        "entities": [
            {"type": "arc", "id": "A1", "name": "Arc One"},
            {"type": "npc", "id": "N1", "name": "Asha"},
        ],
    }

    result = validate_reference_graph(hierarchy, campaign={"id": "C1"})

    assert [entity.identifier for entity in result.entities] == ["C1", "A1", "N1"]
    assert [reference.reference_value for reference in result.references] == ["A1"]
    assert result.diagnostics.visited_campaigns == 1
    assert result.diagnostics.visited_arcs == 1
    assert result.diagnostics.visited_references == 1


def test_validate_reference_graph_walks_explicit_children_without_optional_collections():
    """Verify missing optional collections are treated as empty while siblings scan."""
    hierarchy = {
        "type": "campaign",
        "id": "C1",
        "arcs": [
            {
                "type": "arc",
                "id": "A2",
                "name": "Second Arc",
                "location_refs": ["L2"],
                "locations": [{"type": "location", "id": "L2"}],
            },
            {
                "type": "arc",
                "id": "A1",
                "name": "First Arc",
                "scenario_refs": ["S1"],
                "scenarios": [
                    {
                        "type": "scenario",
                        "id": "S1",
                        "npc_refs": ["N1"],
                        "npcs": [{"type": "npc", "id": "N1"}],
                    }
                ],
            },
        ],
    }

    result = validate_reference_graph(hierarchy, campaign={"id": "C1"})

    assert [entity.identifier for entity in result.entities] == [
        "C1",
        "A1",
        "S1",
        "N1",
        "A2",
        "L2",
    ]
    assert [reference.reference_value for reference in result.references] == [
        "S1",
        "N1",
        "L2",
    ]
    assert result.issues == ()
    assert result.diagnostics.visited_arcs == 2
    assert result.diagnostics.visited_scenarios == 1
    assert result.diagnostics.visited_references == 3
