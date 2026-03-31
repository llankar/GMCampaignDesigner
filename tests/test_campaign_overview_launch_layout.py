"""Regression tests for campaign overview launch layout."""

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


def test_campaign_overview_layout_helper_primes_banner_and_pcs() -> None:
    """Verify that campaign overview layout helper primes banner and PCs."""
    method = _get_method("_prepare_campaign_overview_layout")
    calls = [node for node in ast.walk(method) if isinstance(node, ast.Call)]

    assert any(
        isinstance(call.func, ast.Attribute)
        and isinstance(call.func.value, ast.Name)
        and call.func.value.id == "self"
        and call.func.attr == "_prime_content_frames_for_gm_screen"
        for call in calls
    )
    assert any(
        isinstance(call.func, ast.Name)
        and call.func.id == "display_pcs_in_banner"
        for call in calls
    )


def test_open_campaign_graph_view_prepares_center_layout_before_selecting_parent() -> None:
    """Verify that open campaign graph view prepares center layout before selecting parent."""
    method = _get_method("open_campaign_graph_view")
    call_names: list[str] = []

    class _CallVisitor(ast.NodeVisitor):
        def visit_Call(self, node: ast.Call) -> None:
            """Handle visit call."""
            if isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name) and node.func.value.id == "self":
                call_names.append(node.func.attr)
            self.generic_visit(node)

    _CallVisitor().visit(method)

    assert "clear_current_content" in call_names
    assert "_prepare_campaign_overview_layout" in call_names
    assert "get_content_container" in call_names
    assert call_names.index("clear_current_content") < call_names.index("_prepare_campaign_overview_layout")
    assert call_names.index("_prepare_campaign_overview_layout") < call_names.index("get_content_container")


def test_open_campaign_graph_view_builds_hidden_content_before_gridding() -> None:
    """Verify that open campaign graph view builds hidden content before gridding."""
    method = _get_method("open_campaign_graph_view")
    call_names: list[str] = []

    class _CallVisitor(ast.NodeVisitor):
        def visit_Call(self, node: ast.Call) -> None:
            """Handle visit call."""
            if isinstance(node.func, ast.Attribute):
                if isinstance(node.func.value, ast.Name) and node.func.value.id == "self":
                    call_names.append(f"self.{node.func.attr}")
                elif isinstance(node.func.value, ast.Name) and node.func.value.id == "container":
                    call_names.append(f"container.{node.func.attr}")
            self.generic_visit(node)

    _CallVisitor().visit(method)

    assert "self._build_hidden_main_content" in call_names
    assert "container.grid" in call_names
    assert call_names.index("self._build_hidden_main_content") < call_names.index("container.grid")
