"""Regression tests for timeline simulator dialog."""

from datetime import date

from modules.events.services.timeline_simulator import TimelineSimulationResult
from modules.events.ui.full.timeline_simulator_dialog import format_timeline_result_summary


def test_format_timeline_result_summary_includes_main_counts():
    """Verify that format timeline result summary includes main counts."""
    result = TimelineSimulationResult(
        start_date=date(2026, 3, 10),
        end_date=date(2026, 3, 12),
        days_advanced=2,
        resolved_events=3,
        escalated_factions=1,
        escalated_villains=2,
        advanced_projects=4,
        npc_movements=5,
        change_count=9,
        gm_summary="Timeline advanced with 9 world-state changes.",
        changes=[],
    )

    summary = format_timeline_result_summary(result)

    assert "2026-03-10" in summary
    assert "2026-03-12" in summary
    assert "Resolved events: 3" in summary
    assert "NPC movements: 5" in summary
    assert "world-state changes" in summary
