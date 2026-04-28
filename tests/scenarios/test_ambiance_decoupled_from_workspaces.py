"""Regression checks for ambiance decoupling from workspace add menus."""

from pathlib import Path


def test_gm_screen_add_menu_and_routing_no_longer_reference_ambiance() -> None:
    """GM Screen should not expose workspace-coupled ambiance entries."""
    source = Path("modules/scenarios/gm_screen_view.py").read_text(encoding="utf-8")

    assert "Ambiance Screen" not in source
    assert "open_ambiance_tab" not in source


def test_gm_table_add_menu_and_panel_builder_no_longer_reference_ambiance() -> None:
    """GM Table should not expose ambiance as an add-panel option anymore."""
    source = Path("modules/scenarios/gm_table_view.py").read_text(encoding="utf-8")

    assert "Ambiance Screen" not in source
    assert 'kind == "ambiance"' not in source
    assert "def open_ambiance_panel" not in source
