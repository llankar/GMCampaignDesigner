"""Regression tests for session prep summary."""

import sys
import importlib.util
from pathlib import Path

MODULE_PATH = Path("modules/scenarios/gm_screen/dashboard/session_prep/session_prep_summary.py")
spec = importlib.util.spec_from_file_location("session_prep_summary", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
sys.modules[spec.name] = module
spec.loader.exec_module(module)
build_session_prep_summary = module.build_session_prep_summary


def test_build_session_prep_summary_extracts_priority_sections():
    """Verify that build session prep summary extracts priority sections."""
    fields = [
        {"name": "MainObjective", "type": "longtext", "value": "Stop the ritual\nSecure artifact"},
        {
            "name": "Arcs",
            "type": "longtext",
            "value": [
                {"name": "Arc Alpha", "status": "In Progress", "objective": "Track cult leaders"},
                {"name": "Arc Beta", "status": "Planned", "objective": "Prepare defenses"},
            ],
        },
        {"name": "CriticalNPCs", "type": "list", "values": ["Captain Rhea"]},
        {"name": "CriticalPlaces", "type": "longtext", "value": "Old Watchtower"},
    ]

    summary = build_session_prep_summary(fields)

    assert summary.active_objectives == ["Stop the ritual", "Secure artifact"]
    assert summary.in_progress_arcs == ["Arc Alpha — Track cult leaders"]
    assert summary.critical_reminders == ["Captain Rhea", "Old Watchtower"]


def test_build_session_prep_summary_dedupes_and_handles_missing_arcs():
    """Verify that build session prep summary dedupes and handles missing arcs."""
    fields = [
        {"name": "CurrentGoals", "type": "longtext", "value": "Protect envoy\nProtect envoy"},
        {"name": "NPC Reminders", "type": "longtext", "value": "• Watch Selene\nWatch Selene"},
    ]

    summary = build_session_prep_summary(fields)

    assert summary.active_objectives == ["Protect envoy"]
    assert summary.in_progress_arcs == []
    assert summary.critical_reminders == ["PNJ: Watch Selene"]
