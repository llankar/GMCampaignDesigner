"""Tests for GM Table layout persistence."""

from __future__ import annotations

import json

from modules.scenarios.gm_table.layout_store import GMTableLayoutStore


def test_layout_store_round_trips_table_layout_with_metadata(monkeypatch, tmp_path) -> None:
    """Table layouts should persist across store instances."""
    monkeypatch.setattr(
        "modules.scenarios.gm_table.layout_store.ConfigHelper.get_campaign_dir",
        lambda: str(tmp_path),
    )

    first = GMTableLayoutStore()
    first.save_table_layout(
        "table_1",
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
    loaded = second.get_table_layout("table_1")

    assert loaded["panels"][0]["title"] == "Session Notes"
    assert loaded["panels"][0]["state"]["text"] == "Track the clues"


def test_layout_store_can_clear_table_layout_with_metadata(monkeypatch, tmp_path) -> None:
    """Layouts should be removable per table."""
    monkeypatch.setattr(
        "modules.scenarios.gm_table.layout_store.ConfigHelper.get_campaign_dir",
        lambda: str(tmp_path),
    )

    store = GMTableLayoutStore()
    store.save_table_layout("table_1", {"panels": [{"panel_id": "p1", "kind": "note", "title": "A", "state": {}}]})
    store.clear_table_layout("table_1")

    reloaded = GMTableLayoutStore()
    assert reloaded.get_table_layout("table_1") == {}


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
    store.save_table_layout("table_1", payload)

    loaded = GMTableLayoutStore().get_table_layout("table_1")

    assert loaded["camera"] == payload["camera"]
    assert loaded["home_camera"] == payload["home_camera"]
    assert loaded["bookmarks"] == payload["bookmarks"]


def test_layout_store_round_trips_table_layout(monkeypatch, tmp_path) -> None:
    """Table layouts should persist by stable table id instead of scenario title."""
    monkeypatch.setattr(
        "modules.scenarios.gm_table.layout_store.ConfigHelper.get_campaign_dir",
        lambda: str(tmp_path),
    )

    first = GMTableLayoutStore()
    first.save_table_layout(
        "table_2",
        {
            "panels": [
                {
                    "panel_id": "panel-2",
                    "kind": "note",
                    "title": "Table Notes",
                    "state": {"text": "Shared table context"},
                }
            ]
        },
    )

    second = GMTableLayoutStore()
    loaded = second.get_table_layout("table_2")

    assert loaded["panels"][0]["title"] == "Table Notes"
    assert loaded["panels"][0]["state"]["text"] == "Shared table context"


def test_layout_store_writes_table_first_schema(monkeypatch, tmp_path) -> None:
    """New GM Table persistence should use table ids as the primary layout keys."""
    monkeypatch.setattr(
        "modules.scenarios.gm_table.layout_store.ConfigHelper.get_campaign_dir",
        lambda: str(tmp_path),
    )

    store = GMTableLayoutStore()
    store.save_table_layout("table_3", {"panels": []})

    assert store.data == {"tables": {"table_3": {"panels": []}}, "global": {}}


def test_layout_store_can_clear_table_layout(monkeypatch, tmp_path) -> None:
    """Layouts should be removable per stable table id."""
    monkeypatch.setattr(
        "modules.scenarios.gm_table.layout_store.ConfigHelper.get_campaign_dir",
        lambda: str(tmp_path),
    )

    store = GMTableLayoutStore()
    store.save_table_layout("table_4", {"panels": [{"panel_id": "p1"}]})
    store.clear_table_layout("table_4")

    assert GMTableLayoutStore().get_table_layout("table_4") == {}


def test_layout_store_preserves_legacy_scenarios_block(monkeypatch, tmp_path) -> None:
    """Legacy scenario layouts should remain available in memory for migration."""
    monkeypatch.setattr(
        "modules.scenarios.gm_table.layout_store.ConfigHelper.get_campaign_dir",
        lambda: str(tmp_path),
    )
    layout_path = tmp_path / GMTableLayoutStore.FILE_NAME
    layout_path.write_text(
        json.dumps(
            {
                "tables": {"table_1": {"panels": []}},
                "global": {},
                "scenarios": {"Night Run": {"panels": [{"panel_id": "legacy"}]}},
            }
        ),
        encoding="utf-8",
    )

    store = GMTableLayoutStore()

    assert store.data["scenarios"]["Night Run"]["panels"][0]["panel_id"] == "legacy"


def test_layout_store_reads_bare_legacy_scenario_mapping(monkeypatch, tmp_path) -> None:
    """Very old bare scenario mappings should still load for migration."""
    monkeypatch.setattr(
        "modules.scenarios.gm_table.layout_store.ConfigHelper.get_campaign_dir",
        lambda: str(tmp_path),
    )
    layout_path = tmp_path / GMTableLayoutStore.FILE_NAME
    layout_path.write_text(
        json.dumps({"Night Run": {"panels": [{"panel_id": "legacy"}]}}),
        encoding="utf-8",
    )

    store = GMTableLayoutStore()

    assert store.data["scenarios"]["Night Run"]["panels"][0]["panel_id"] == "legacy"


def test_layout_store_persists_custom_table_names(monkeypatch, tmp_path) -> None:
    """Custom table names should live in global table_names with defaults as fallback."""
    monkeypatch.setattr(
        "modules.scenarios.gm_table.layout_store.ConfigHelper.get_campaign_dir",
        lambda: str(tmp_path),
    )

    store = GMTableLayoutStore()
    assert store.get_table_name("table_1") == "Main"
    assert store.get_table_name("table_6") == "Table6"

    store.save_table_name("table_2", "Shadow Crew")
    reloaded = GMTableLayoutStore()

    assert reloaded.get_table_name("table_2") == "Shadow Crew"
    assert reloaded.data["global"]["table_names"] == {"table_2": "Shadow Crew"}


def test_layout_store_clears_default_table_names_from_global(monkeypatch, tmp_path) -> None:
    """Saving a default or blank name should remove custom table name metadata."""
    monkeypatch.setattr(
        "modules.scenarios.gm_table.layout_store.ConfigHelper.get_campaign_dir",
        lambda: str(tmp_path),
    )

    store = GMTableLayoutStore()
    store.save_table_name("table_5", "Dungeon Team")
    store.save_table_name("table_5", "Table5")

    assert GMTableLayoutStore().get_table_name("table_5") == "Table5"
    assert GMTableLayoutStore().get_global_setting("table_names") == {}


def test_layout_store_round_trips_fixed_overlay_state(monkeypatch, tmp_path) -> None:
    """Fixed overlay state should persist separately from regular panels."""
    monkeypatch.setattr(
        "modules.scenarios.gm_table.layout_store.ConfigHelper.get_campaign_dir",
        lambda: str(tmp_path),
    )
    payload = {
        "panels": [],
        "fixed_overlay": {
            "visible": True,
            "collapsed": False,
            "width": 380,
            "anchor": "left",
            "selected_item_ids": ["fixed-1"],
            "items": [{"item_id": "fixed-1", "kind": "note", "title": "Pinned Table", "state": {"text": "A"}}],
        },
    }
    store = GMTableLayoutStore()
    store.save_table_layout("table_1", payload)
    assert GMTableLayoutStore().get_table_layout("table_1")["fixed_overlay"] == payload["fixed_overlay"]


def test_layout_store_round_trips_pdf_viewer_panel_state(monkeypatch, tmp_path) -> None:
    """PDF viewer panel state should remain JSON-safe."""
    monkeypatch.setattr(
        "modules.scenarios.gm_table.layout_store.ConfigHelper.get_campaign_dir",
        lambda: str(tmp_path),
    )
    payload = {"panels": [{"panel_id": "pdf-1", "kind": "pdf_viewer", "title": "Rules", "state": {"pdf_path": "rules.pdf", "current_page": 3, "zoom": 1.5}}]}
    store = GMTableLayoutStore(); store.save_table_layout("table_1", payload)
    assert GMTableLayoutStore().get_table_layout("table_1")["panels"][0]["state"]["current_page"] == 3


def test_layout_store_uses_atomic_write_for_table_layouts(monkeypatch, tmp_path) -> None:
    """Layout writes should replace a temp file atomically."""
    monkeypatch.setattr(
        "modules.scenarios.gm_table.layout_store.ConfigHelper.get_campaign_dir",
        lambda: str(tmp_path),
    )
    calls = []
    real_replace = __import__("os").replace
    def capture_replace(src, dst):
        calls.append((src, dst)); real_replace(src, dst)
    monkeypatch.setattr("modules.scenarios.gm_table.layout_store.os.replace", capture_replace)
    GMTableLayoutStore().save_table_layout("table_1", {"panels": []})
    assert calls and calls[0][0].endswith("gm_table_layouts.json.tmp")
