"""Tests for GM Table layout persistence."""

from __future__ import annotations

from modules.scenarios.gm_table.layout_store import GMTableLayoutStore


def test_layout_store_round_trips_scenario_layout(monkeypatch, tmp_path) -> None:
    """Scenario layouts should persist across store instances."""
    monkeypatch.setattr(
        "modules.scenarios.gm_table.layout_store.ConfigHelper.get_campaign_dir",
        lambda: str(tmp_path),
    )

    first = GMTableLayoutStore()
    first.save_scenario_layout(
        "Night Run",
        {
            "panels": [
                {
                    "panel_id": "panel-1",
                    "kind": "note",
                    "title": "Session Notes",
                    "state": {"x": 24, "y": 36, "width": 420, "height": 280, "text": "Track the clues"},
                }
            ]
        },
    )

    second = GMTableLayoutStore()
    loaded = second.get_scenario_layout("Night Run")

    assert loaded["panels"][0]["title"] == "Session Notes"
    assert loaded["panels"][0]["state"]["text"] == "Track the clues"


def test_layout_store_can_clear_layout(monkeypatch, tmp_path) -> None:
    """Layouts should be removable per scenario."""
    monkeypatch.setattr(
        "modules.scenarios.gm_table.layout_store.ConfigHelper.get_campaign_dir",
        lambda: str(tmp_path),
    )

    store = GMTableLayoutStore()
    store.save_scenario_layout("Night Run", {"panels": [{"panel_id": "p1", "kind": "note", "title": "A", "state": {}}]})
    store.clear_scenario_layout("Night Run")

    reloaded = GMTableLayoutStore()
    assert reloaded.get_scenario_layout("Night Run") == {}
