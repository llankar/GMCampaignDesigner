"""Tests for GM Table handout collection service."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import modules.scenarios.gm_table.handouts.service as service_module


def _wrapper(items):
    return SimpleNamespace(load_items=lambda: items)


def test_collect_scenario_handouts_collects_maps_and_portraits_with_dedupe_and_order(monkeypatch, tmp_path) -> None:
    """Service should gather linked portraits/maps, skip missing, dedupe, and keep deterministic order."""
    aria = tmp_path / "aria.png"
    zara = tmp_path / "zara.png"
    map_img = tmp_path / "city-map.png"
    aria.write_bytes(b"png")
    zara.write_bytes(b"png")
    map_img.write_bytes(b"png")

    monkeypatch.setattr(service_module, "parse_portrait_value", lambda value: [str(value)] if value else [])
    monkeypatch.setattr(service_module, "resolve_portrait_candidate", lambda value, _campaign_dir: value)

    wrappers = {
        "NPCs": _wrapper(
            [
                {"Name": "Zara", "Portrait": str(zara)},
                {"Name": "Aria", "Portrait": str(aria)},
                {"Name": "Ghost", "Portrait": str(tmp_path / "missing.png")},
                {"Name": "Echo", "Portrait": str(zara)},
            ]
        ),
        "Creatures": _wrapper([]),
        "Villains": _wrapper([]),
        "Places": _wrapper([]),
        "Bases": _wrapper([]),
        "PCs": _wrapper([]),
        "Factions": _wrapper([]),
    }
    map_wrapper = _wrapper([{"Name": "City", "Image": str(map_img)}])

    scenario = {
        "NPCs": ["Zara", "Aria", "Ghost", "Echo"],
        "Maps": ["City"],
    }

    handouts = service_module.collect_scenario_handouts(scenario, wrappers, map_wrapper)

    assert [item.path for item in handouts] == [str(map_img.resolve()), str(zara.resolve()), str(aria.resolve())]
    assert [item.kind for item in handouts] == ["map", "portrait", "portrait"]
    assert all(Path(item.path).exists() for item in handouts)
    assert len({item.path for item in handouts}) == len(handouts)
