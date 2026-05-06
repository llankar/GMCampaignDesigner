"""Regression tests for ambiguous-reference validation dialog helpers."""

from src.ui.validation import (
    ValidationWizardController,
    ValidationWizardIssue,
    ValidationWizardStatus,
    resolve_reference_for_issue,
)
from src.ui.validation.dialogs import (
    AmbiguousReferenceDialog,
    AmbiguousReferenceDialogConfig,
)
from src.validation import validate_reference_graph


def _ambiguous_wizard():
    hierarchy = {
        "type": "arc",
        "id": "A1",
        "scenario_refs": ["Duplicate"],
        "scenarios": [
            {
                "type": "scenario",
                "id": "S1",
                "name": "Duplicate",
                "description": "Première piste",
                "tags": ["politique", "intro"],
            },
            {
                "type": "scenario",
                "id": "S2",
                "name": "Duplicate",
                "description": "Piste alternative",
                "tags": "combat, nuit",
            },
            {"type": "scenario", "id": "S3", "name": "Duplicate"},
        ],
    }
    graph = validate_reference_graph(hierarchy)
    reference = resolve_reference_for_issue(graph.issues[0], graph.references)
    controller = ValidationWizardController(
        [ValidationWizardIssue(issue=graph.issues[0], reference=reference)]
    )
    controller.start()
    return hierarchy, graph, controller


def test_dialog_normalizes_candidates_and_displays_two_side_by_side():
    hierarchy, graph, controller = _ambiguous_wizard()

    dialog = AmbiguousReferenceDialog(
        None,
        controller,
        graph.issues[0],
        config=AmbiguousReferenceDialogConfig(candidates=graph.entities[1:]),
    )

    assert len(dialog.candidates) == 3
    assert [candidate.identifier for candidate in dialog.displayed_candidates] == [
        "S1",
        "S2",
    ]
    assert dialog.displayed_candidates[0].display_name == "Duplicate"
    assert dialog.displayed_candidates[0].display_path.endswith("scenario:S1")
    assert dialog.displayed_candidates[0].key_infos == (
        "Première piste",
        "Tags : politique, intro",
    )
    assert hierarchy["scenario_refs"] == ["Duplicate"]


def test_choose_right_returns_selected_identifier_to_controller_for_immediate_remap():
    hierarchy, graph, controller = _ambiguous_wizard()
    observed_steps = []
    dialog = AmbiguousReferenceDialog(
        None,
        controller,
        graph.issues[0],
        config=AmbiguousReferenceDialogConfig(
            candidates=graph.entities[1:],
            on_step=observed_steps.append,
        ),
    )

    step = dialog.choose_right()

    assert step.status == ValidationWizardStatus.COMPLETED
    assert dialog.selected_identifier == "S2"
    assert hierarchy["scenario_refs"] == ["S2"]
    assert [observed.status for observed in observed_steps] == [
        ValidationWizardStatus.COMPLETED
    ]


def test_show_other_candidates_callback_receives_all_candidates_and_ignore_skips_issue():
    hierarchy, graph, controller = _ambiguous_wizard()
    received = []
    errors = []
    dialog = AmbiguousReferenceDialog(
        None,
        controller,
        graph.issues[0],
        config=AmbiguousReferenceDialogConfig(
            candidates=graph.entities[1:],
            on_show_other_candidates=lambda issue, candidates: received.append(candidates),
            on_error=errors.append,
        ),
    )

    dialog.show_other_candidates()
    step = dialog.ignore()

    assert errors == []
    assert len(received[0]) == 3
    assert step.status == ValidationWizardStatus.COMPLETED
    assert controller.summary.skipped_session == 1
    assert hierarchy["scenario_refs"] == ["Duplicate"]


def test_payload_candidate_strings_are_usable_when_no_provider_is_configured():
    hierarchy, graph, controller = _ambiguous_wizard()

    dialog = AmbiguousReferenceDialog(None, controller, graph.issues[0])

    assert [candidate.identifier for candidate in dialog.displayed_candidates] == [
        "S1",
        "S2",
    ]
    assert all(
        candidate.entity_type == "scenario"
        for candidate in dialog.displayed_candidates
    )
