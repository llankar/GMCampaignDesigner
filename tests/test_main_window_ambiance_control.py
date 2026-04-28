"""Static regression checks for MainWindow ambiance entrypoint wiring."""

from __future__ import annotations

import ast
from pathlib import Path


def _get_open_ambiance_panel_source() -> str:
    source = Path("main_window.py").read_text(encoding="utf-8-sig")
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "MainWindow":
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == "open_ambiance_panel":
                    return ast.get_source_segment(source, item) or ""
    raise AssertionError("MainWindow.open_ambiance_panel not found")


def test_open_ambiance_panel_uses_standalone_control_window() -> None:
    """Entrypoint should only manage a standalone ambiance toplevel."""
    method_source = _get_open_ambiance_panel_source()

    assert "AmbianceControlWindow(self)" in method_source
    assert "_ambiance_control_window" in method_source
    assert "window.lift()" in method_source
    assert "window.focus_force()" in method_source


def test_open_ambiance_panel_no_longer_routes_to_workspace_views() -> None:
    """MainWindow entrypoint should not depend on GM Screen/Table instances."""
    method_source = _get_open_ambiance_panel_source()

    assert "current_gm_view" not in method_source
    assert "current_gm_table" not in method_source
    assert "open_gm_screen" not in method_source
