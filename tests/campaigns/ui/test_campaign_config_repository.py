"""Regression tests for campaign config repository."""

import sqlite3

from modules.campaigns.ui.graphical_display.services.persistence import campaign_config_repository as repository_module
from modules.campaigns.ui.graphical_display.services.persistence.campaign_config_repository import (
    CampaignConfigRepository,
)


class _ConnectionFactory:
    def __init__(self):
        """Initialize the _ConnectionFactory instance."""
        self.conn = sqlite3.connect(":memory:")

    def __call__(self):
        """Invoke the instance like a callable."""
        return self.conn


def test_repository_roundtrip_persists_overview_focus_in_campaign_config(monkeypatch):
    """Verify that repository roundtrip persists overview focus in campaign config."""
    factory = _ConnectionFactory()
    monkeypatch.setattr(repository_module, "get_connection", factory)
    repository = CampaignConfigRepository()

    repository.save_overview_focus("Campaign A", arc_name="Arc 1", scenario_title="Scenario X")
    arc_name, scenario_title = repository.load_overview_focus("Campaign A")

    assert arc_name == "Arc 1"
    assert scenario_title == "Scenario X"

    cursor = factory.conn.cursor()
    cursor.execute(
        """
        SELECT overview_selected_arc, overview_selected_scenario
        FROM campaign_config
        WHERE campaign_name = ?
        """,
        ("Campaign A",),
    )
    assert cursor.fetchone() == ("Arc 1", "Scenario X")
