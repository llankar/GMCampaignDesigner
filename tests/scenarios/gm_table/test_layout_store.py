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


def test_layout_store_round_trips_camera_and_bookmarks(monkeypatch, tmp_path) -> None:
    """Infinite desk camera metadata should persist unchanged through the layout store."""
    monkeypatch.setattr(
        "modules.scenarios.gm_table.layout_store.ConfigHelper.get_campaign_dir",
        lambda: str(tmp_path),
    )

    store = GMTableLayoutStore()
    payload = {
        "camera": {"x": 120.0, "y": 80.0, "zoom": 0.85},
        "home_camera": {"x": -60.0, "y": -40.0, "zoom": 1.0},
        "bookmarks": [
            {"name": "North Wing", "x": 320.0, "y": 180.0, "zoom": 0.9},
            {"name": "War Room", "x": 900.0, "y": 420.0, "zoom": 1.1},
        ],
        "panels": [],
    }
    store.save_scenario_layout("Night Run", payload)

    loaded = GMTableLayoutStore().get_scenario_layout("Night Run")

    assert loaded["camera"] == payload["camera"]
    assert loaded["home_camera"] == payload["home_camera"]
    assert loaded["bookmarks"] == payload["bookmarks"]
