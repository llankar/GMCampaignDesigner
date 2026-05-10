"""Regression tests for PC banner text safety."""
from __future__ import annotations

import ast
from pathlib import Path


SOURCE_PATH = Path("modules/pcs/display_pcs.py")
MODULE_AST = ast.parse(SOURCE_PATH.read_text(encoding="utf-8"))


def test_pc_banner_imports_shared_tk_text_safety() -> None:
    """The PC banner should use shared bounded text helpers before rendering labels."""

    imports = [node for node in MODULE_AST.body if isinstance(node, ast.ImportFrom)]

    assert any(
        node.module == "modules.helpers.tk_text_safety"
        and {alias.name for alias in node.names}
        >= {"LABEL_DISPLAY_LIMIT", "LONGFORM_DISPLAY_LIMIT", "safe_display_text"}
        for node in imports
    )


def test_pc_banner_sanitizes_label_text_before_ctk_label_creation() -> None:
    """Header and body labels should not receive raw database text."""

    calls = [node for node in ast.walk(MODULE_AST) if isinstance(node, ast.Call)]
    ctk_label_calls = [
        call
        for call in calls
        if isinstance(call.func, ast.Attribute) and call.func.attr == "CTkLabel"
    ]
    text_keywords = [keyword.value for call in ctk_label_calls for keyword in call.keywords if keyword.arg == "text"]

    safe_text_calls = [
        value
        for value in text_keywords
        if isinstance(value, ast.Call) and isinstance(value.func, ast.Name) and value.func.id == "safe_display_text"
    ]

    assert len(safe_text_calls) >= 2
    assert any(
        any(
            keyword.arg == "max_chars"
            and isinstance(keyword.value, ast.Name)
            and keyword.value.id == "LABEL_DISPLAY_LIMIT"
            for keyword in call.keywords
        )
        for call in safe_text_calls
    )
    assert any(
        any(
            keyword.arg == "max_chars"
            and isinstance(keyword.value, ast.Name)
            and keyword.value.id == "LONGFORM_DISPLAY_LIMIT"
            for keyword in call.keywords
        )
        for call in safe_text_calls
    )
