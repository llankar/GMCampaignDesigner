"""Regression tests for interactive reference fix actions."""

from src.services import ReferenceActionResult, ReferenceFixService
from src.validation import validate_reference_graph


def _reference_for(hierarchy, value):
    graph = validate_reference_graph(hierarchy, campaign={"id": "sample"})
    return next(reference for reference in graph.references if reference.reference_value == value)


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
    assert result.changes_applied == ("C1.arc_refs: Missing Arc → A1",)
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
    assert result.changes_applied == ("C1.arc_refs: référence supprimée",)


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
        "scenarios: entité ajoutée",
        "A1.scenario_refs: Missing Scenario → S1",
    )
