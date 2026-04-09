"""Tests for GM Screen 2 desktop layout engine."""

from modules.scenarios.gm_screen2.ui.layout.desktop_layout_engine import DesktopLayoutEngine


def test_layout_engine_distributes_visible_panels_with_normalized_ratios():
    engine = DesktopLayoutEngine()

    geometry = engine.compute(
        panel_ids=["overview", "entities", "notes"],
        split_ratios=[2.0, 1.0, 1.0],
        hidden_panels=set(),
    )

    assert len(geometry) == 3
    assert geometry[0].panel_id == "overview"
    assert round(geometry[0].relwidth, 2) == 0.5
    assert round(geometry[1].relx, 2) == 0.5


def test_layout_engine_skips_hidden_panels():
    engine = DesktopLayoutEngine()

    geometry = engine.compute(
        panel_ids=["overview", "entities", "notes"],
        split_ratios=[1.0, 1.0, 1.0],
        hidden_panels={"entities"},
    )

    assert [item.panel_id for item in geometry] == ["overview", "notes"]
