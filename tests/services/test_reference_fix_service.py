"""Regression tests for interactive reference fix actions."""

from src.services import ReferenceActionResult, ReferenceFixService
from src.validation import validate_reference_graph


def _reference_for(hierarchy, value):
    graph = validate_reference_graph(hierarchy, campaign={"id": "sample"})
    return next(reference for reference in graph.references if reference.reference_value == value)


def _invalid_hierarchy_reference_and_target(hierarchy, value):
    graph = validate_reference_graph(hierarchy, campaign={"id": "sample"})
    issue = next(issue for issue in graph.issues if issue.payload.referenced_name == value)
    reference = next(
        reference
        for reference in graph.references
        if reference.reference_value == value
    )
    target = next(entity for entity in graph.entities if entity.path == tuple(issue.payload.target_path))
    return reference, target


def test_remap_reference_updates_selected_list_occurrence_and_reports_contract():
    hierarchy = {
        "type": "campaign",
        "id": "C1",
        "arc_refs": ["Missing Arc"],
        "arcs": [{"type": "arc", "id": "A1", "name": "Arc One"}],
    }
    reference = _reference_for(hierarchy, "Missing Arc")

    result = ReferenceFixService().remap_reference(reference, "A1")

    assert isinstance(result, ReferenceActionResult)
    assert result.success is True
    assert hierarchy["arc_refs"] == ["A1"]
    assert result.changes_applied == ("C1.arc_refs: Missing Arc -> A1",)
    assert "A1" in result.ui_message


def test_remap_reference_preserves_mapping_shape_and_updates_declared_type():
    hierarchy = {
        "type": "arc",
        "id": "A1",
        "scenario_refs": [{"ref": "Wrong", "type": "location", "note": "keep"}],
    }
    reference = _reference_for(hierarchy, "Wrong")

    result = ReferenceFixService().remap_reference(
        reference,
        {"type": "scenario", "id": "S1"},
    )

    assert result.success is True
    assert hierarchy["scenario_refs"] == [
        {"ref": "S1", "type": "scenario", "note": "keep"}
    ]


def test_remove_reference_deletes_only_the_selected_occurrence():
    hierarchy = {
        "type": "campaign",
        "id": "C1",
        "arc_refs": ["A1", "Missing Arc", "A2"],
    }
    reference = _reference_for(hierarchy, "Missing Arc")

    result = ReferenceFixService().remove_reference(reference)

    assert result.success is True
    assert hierarchy["arc_refs"] == ["A1", "A2"]
    assert result.changes_applied == ("C1.arc_refs: reference removed",)


def test_link_created_entity_attaches_child_and_remaps_reference():
    hierarchy = {
        "type": "arc",
        "id": "A1",
        "scenario_refs": ["Missing Scenario"],
    }
    new_entity = {"type": "scenario", "id": "S1", "name": "New Scenario"}
    reference = _reference_for(hierarchy, "Missing Scenario")

    result = ReferenceFixService().link_created_entity(reference, new_entity)

    assert result.success is True
    assert hierarchy["scenario_refs"] == ["S1"]
    assert hierarchy["scenarios"] == [new_entity]
    assert result.changes_applied == (
        "scenarios: entity added",
        "A1.scenario_refs: Missing Scenario -> S1",
    )


def test_attach_existing_entity_moves_target_under_source_without_remapping():
    hierarchy = {
        "type": "campaign",
        "id": "C1",
        "arcs": [
            {
                "type": "arc",
                "id": "A1",
                "location_refs": ["Sibling Place"],
                "locations": [
                    {"type": "location", "id": "L1", "name": "Local Place"}
                ],
            },
            {
                "type": "arc",
                "id": "A2",
                "locations": [
                    {"type": "location", "id": "L2", "name": "Sibling Place"}
                ],
            },
        ],
    }
    reference, target = _invalid_hierarchy_reference_and_target(
        hierarchy, "Sibling Place"
    )
    service = ReferenceFixService()

    assert service.can_attach_existing_entity(reference, target) is True
    result = service.attach_existing_entity(reference, target)

    assert result.success is True
    assert hierarchy["arcs"][0]["location_refs"] == ["Sibling Place"]
    assert [location["id"] for location in hierarchy["arcs"][0]["locations"]] == [
        "L1",
        "L2",
    ]
    assert hierarchy["arcs"][1]["locations"] == []
    assert result.changes_applied == ("A1.locations: L2 attached",)


def test_attach_existing_entity_is_hidden_when_target_left_recorded_origin():
    hierarchy = {
        "type": "campaign",
        "id": "C1",
        "arcs": [
            {
                "type": "arc",
                "id": "A1",
                "location_refs": ["Sibling Place"],
            },
            {
                "type": "arc",
                "id": "A2",
                "locations": [
                    {"type": "location", "id": "L2", "name": "Sibling Place"}
                ],
            },
            {
                "type": "arc",
                "id": "A3",
                "location_refs": ["Sibling Place"],
            },
        ],
    }
    graph = validate_reference_graph(hierarchy, campaign={"id": "sample"})
    target = next(entity for entity in graph.entities if entity.identifier == "L2")
    first_reference = next(
        reference
        for reference in graph.references
        if reference.source.identifier == "A1"
    )
    stale_reference = next(
        reference
        for reference in graph.references
        if reference.source.identifier == "A3"
    )
    service = ReferenceFixService()

    assert service.attach_existing_entity(first_reference, target).success is True

    assert service.can_attach_existing_entity(stale_reference, target) is False


def test_attach_existing_entity_rejects_equivalent_target_already_under_source():
    hierarchy = {
        "type": "campaign",
        "id": "C1",
        "arcs": [
            {
                "type": "arc",
                "id": "A1",
                "location_refs": ["Sibling Place"],
                "locations": [
                    {"type": "location", "id": "L2", "name": "Local Alias"}
                ],
            },
            {
                "type": "arc",
                "id": "A2",
                "locations": [
                    {"type": "location", "id": "L2", "name": "Sibling Place"}
                ],
            },
        ],
    }
    reference, target = _invalid_hierarchy_reference_and_target(
        hierarchy, "Sibling Place"
    )
    service = ReferenceFixService()

    assert service.can_attach_existing_entity(reference, target) is False
    result = service.attach_existing_entity(reference, target)

    assert result.success is False
    assert [location["name"] for location in hierarchy["arcs"][0]["locations"]] == [
        "Local Alias"
    ]
    assert [location["name"] for location in hierarchy["arcs"][1]["locations"]] == [
        "Sibling Place"
    ]


def test_attach_existing_entity_rejects_same_label_already_under_source():
    hierarchy = {
        "type": "campaign",
        "id": "C1",
        "arcs": [
            {
                "type": "arc",
                "id": "A1",
                "location_refs": ["L2"],
                "locations": [
                    {"type": "location", "id": "L1", "name": "Sibling Place"}
                ],
            },
            {
                "type": "arc",
                "id": "A2",
                "locations": [
                    {"type": "location", "id": "L2", "name": "Sibling Place"}
                ],
            },
        ],
    }
    reference, target = _invalid_hierarchy_reference_and_target(hierarchy, "L2")
    service = ReferenceFixService()

    assert service.can_attach_existing_entity(reference, target) is False
    result = service.attach_existing_entity(reference, target)

    assert result.success is False
    assert [location["id"] for location in hierarchy["arcs"][0]["locations"]] == ["L1"]
    assert [location["id"] for location in hierarchy["arcs"][1]["locations"]] == ["L2"]
