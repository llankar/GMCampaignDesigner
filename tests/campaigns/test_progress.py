"""Regression tests for campaign advancement progress helpers."""

from modules.campaigns.shared.progress import (
    arc_progress_from_scenarios,
    campaign_progress_from_arcs,
    status_progress,
)


def test_status_progress_counts_only_completed_statuses():
    """Verify only completed scenario statuses count as finished progress."""
    assert status_progress("Planned") == 0.0
    assert status_progress("running") == 0.0
    assert status_progress("Paused") == 0.0
    assert status_progress("completed") == 1.0
    assert status_progress("done") == 1.0
    assert status_progress("") == 0.0
    assert status_progress("nonsense") == 0.0


def test_arc_progress_counts_completed_linked_scenarios_and_empty_arcs_are_zero():
    """Verify arc advancement comes from completed linked scenario statuses."""
    assert arc_progress_from_scenarios([]) == 0.0
    assert arc_progress_from_scenarios([
        {"Status": "Completed"},
        {"Status": "completed"},
        {"Status": "In Progress"},
        {"Status": "Planned"},
    ]) == 0.5


def test_arc_progress_uses_canonical_status_alias_fields():
    """Verify localized/lower-case scenario status fields drive advancement."""
    assert arc_progress_from_scenarios([
        {"Statut": "Completed"},
        {"status": "In Progress"},
        {"ScenarioStatus": "Planned"},
    ]) == 1 / 3


def test_arc_progress_prefers_status_over_stale_statut_field():
    """Verify the real Status field wins when a stale Statut value is present."""
    assert arc_progress_from_scenarios([
        {"Status": "Completed", "Statut": "Planned"},
    ]) == 1.0


def test_campaign_progress_counts_completed_scenarios_across_arcs():
    """Verify campaign advancement uses completed scenarios over all linked scenarios."""
    assert campaign_progress_from_arcs([]) == 0.0
    assert campaign_progress_from_arcs([{"scenarios": []}]) == 0.0

    arcs = [
        {"scenarios": [{"Status": "Completed"}, {"Status": "In Progress"}]},
        {"scenarios": []},
        {"scenarios": [{"Status": "Completed"}, {"Status": "Planned"}]},
    ]

    assert campaign_progress_from_arcs(arcs) == 0.5
