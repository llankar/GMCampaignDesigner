"""Regression tests for campaign graphical display data helpers."""

from modules.campaigns.shared.progress import campaign_progress_from_arcs
from modules.campaigns.ui.graphical_display.data import build_campaign_graph_payload


def test_campaign_graph_payload_prefers_status_over_stale_statut():
    """Scenario cards and campaign percentages use the canonical Status value."""
    payload = build_campaign_graph_payload(
        {
            "Name": "Test Campaign",
            "Arcs": [{"name": "Act I", "scenarios": ["Opening"]}],
        },
        [{"Title": "Opening", "Status": "Completed", "Statut": "Planned"}],
    )

    assert payload is not None
    assert payload.arcs[0].scenarios[0].status == "Completed"
    assert campaign_progress_from_arcs(payload.arcs) == 1.0
