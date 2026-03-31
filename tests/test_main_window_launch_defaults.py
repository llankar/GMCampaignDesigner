"""Regression tests for main window launch defaults."""

from __future__ import annotations

import ast
from pathlib import Path


SOURCE_PATH = Path("main_window.py")
MODULE_AST = ast.parse(SOURCE_PATH.read_text(encoding="utf-8-sig"))


def _get_main_window_class() -> ast.ClassDef:
    """Return main window class."""
    for node in MODULE_AST.body:
        if isinstance(node, ast.ClassDef) and node.name == "MainWindow":
            return node
    raise AssertionError("MainWindow class not found")


MAIN_WINDOW_CLASS = _get_main_window_class()


def _get_method(name: str) -> ast.FunctionDef:
    """Return method."""
    for node in MAIN_WINDOW_CLASS.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"{name} method not found")


def test_main_window_schedules_campaign_overview_on_launch() -> None:
    """Verify that main window schedules campaign overview on launch."""
    init_method = _get_method("__init__")

    for node in ast.walk(init_method):
        # Process each node from ast.walk(init_method).
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Attribute) or node.func.attr != "after":
            continue
        if len(node.args) != 2:
            continue
        delay_arg, callback_arg = node.args
        if not (isinstance(delay_arg, ast.Constant) and delay_arg.value == 800):
            continue
        if isinstance(callback_arg, ast.Attribute) and callback_arg.attr == "_auto_open_campaign_overview":
            return

    raise AssertionError("MainWindow.__init__ no longer schedules the campaign overview at launch")


def test_gm_screen_auto_open_alias_points_to_campaign_overview() -> None:
    """Verify that GM screen auto open alias points to campaign overview."""
    alias_method = _get_method("_auto_open_gm_screen_if_available")
    calls = [node for node in ast.walk(alias_method) if isinstance(node, ast.Call)]

    assert any(
        isinstance(call.func, ast.Attribute)
        and isinstance(call.func.value, ast.Name)
        and call.func.value.id == "self"
        and call.func.attr == "_auto_open_campaign_overview"
        for call in calls
    )
