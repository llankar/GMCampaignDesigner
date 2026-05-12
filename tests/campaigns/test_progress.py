"""Regression tests for campaign advancement progress helpers."""

from modules.campaigns.shared.progress import (
    arc_progress_from_scenarios,
    campaign_progress_from_arcs,
    status_progress,
)


def test_status_progress_canonicalizes_shared_status_values():
    """Verify aliases, blanks, and invalid values use shared scenario status rules."""
    assert status_progress("Planned") == 0.0
    assert status_progress("running") == 0.5
    assert status_progress("Paused") == 0.5
    assert status_progress("done") == 1.0
    assert status_progress("") == 0.0
    assert status_progress("nonsense") == 0.0


def test_arc_progress_averages_linked_scenario_statuses_and_empty_arcs_are_zero():
    """Verify arc advancement comes from linked scenario statuses."""
    assert arc_progress_from_scenarios([]) == 0.0
    assert arc_progress_from_scenarios([
        {"Status": "Completed"},
        {"Status": "In Progress"},
        {"Status": "Planned"},
    ]) == 0.5


def test_campaign_progress_averages_arc_advancement():
    """Verify campaign advancement averages per-arc scenario advancement."""
    arcs = [
        {"scenarios": [{"Status": "Completed"}, {"Status": "In Progress"}]},
        {"scenarios": []},
    ]

    assert campaign_progress_from_arcs(arcs) == 0.375
