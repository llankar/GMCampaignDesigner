"""Integration guardrails for MainWindow GM Screen 2 entrypoint."""

from __future__ import annotations

import ast
from pathlib import Path


SOURCE_PATH = Path("main_window.py")
MODULE_AST = ast.parse(SOURCE_PATH.read_text(encoding="utf-8-sig"))


def _get_main_window_class() -> ast.ClassDef:
    for node in MODULE_AST.body:
        if isinstance(node, ast.ClassDef) and node.name == "MainWindow":
            return node
    raise AssertionError("MainWindow class not found")


def _get_method(name: str) -> ast.FunctionDef:
    cls = _get_main_window_class()
    for node in cls.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"{name} method not found")


def test_open_gm_screen2_signature_is_stable():
    method = _get_method("open_gm_screen2")
    argument_names = [arg.arg for arg in method.args.args]
    kwonly_names = [arg.arg for arg in method.args.kwonlyargs]

    assert argument_names == ["self"]
    assert kwonly_names == ["show_empty_message", "scenario_name", "initial_layout"]


def test_open_gm_screen2_wires_toolbar_layout_actions_and_workspace_view():
    method = _get_method("open_gm_screen2")
    source = ast.get_source_segment(SOURCE_PATH.read_text(encoding="utf-8-sig"), method) or ""

    assert "GMScreen2Controller" in source
    assert "GMScreen2RootView" in source
    assert "ScenarioPanelPayloadProvider" in source
    assert "Save Preset" in source
    assert "Load Preset" in source
    assert "Reset Layout" in source
