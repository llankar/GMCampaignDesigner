"""Static contracts for the main-window accordion sidebar."""

from __future__ import annotations

import ast
from pathlib import Path


SOURCE_PATH = Path("main_window.py")
MODULE_AST = ast.parse(SOURCE_PATH.read_text(encoding="utf-8-sig"))


def _create_sidebar_method() -> ast.FunctionDef:
    for node in MODULE_AST.body:
        if not isinstance(node, ast.ClassDef) or node.name != "MainWindow":
            continue
        for member in node.body:
            if isinstance(member, ast.FunctionDef) and member.name == "create_accordion_sidebar":
                return member
    raise AssertionError("MainWindow.create_accordion_sidebar not found")


def _assigned_list(method: ast.FunctionDef, variable_name: str) -> ast.List:
    for node in method.body:
        if not isinstance(node, ast.Assign):
            continue
        if any(isinstance(target, ast.Name) and target.id == variable_name for target in node.targets):
            assert isinstance(node.value, ast.List)
            return node.value
    raise AssertionError(f"{variable_name} list not found")


def _item_specs(items: ast.List) -> dict[str, tuple[str, str]]:
    specs: dict[str, tuple[str, str]] = {}
    for element in items.elts:
        if not isinstance(element, ast.Call) or not element.args:
            continue
        label = ast.literal_eval(element.args[1])
        command = element.args[2]
        assert isinstance(command, ast.Attribute)
        specs[label] = (ast.literal_eval(element.args[0]), command.attr)
    return specs


def test_synchronization_destinations_have_a_dedicated_sidebar_section() -> None:
    """Both synchronization routes remain together and directly discoverable."""
    method = _create_sidebar_method()
    synchronization_items = _item_specs(_assigned_list(method, "campaign_synchronization"))

    assert synchronization_items == {
        "Campaign Update Settings": ("campaign_updates", "open_campaign_update_settings"),
        "Cross-campaign Asset Library": (
            "asset_library",
            "open_cross_campaign_asset_library",
        ),
    }

    synchronization_sections = [
        call
        for call in ast.walk(method)
        if isinstance(call, ast.Call)
        and isinstance(call.func, ast.Name)
        and call.func.id == "SidebarSectionSpec"
        and len(call.args) >= 2
        and isinstance(call.args[0], ast.Constant)
        and call.args[0].value == "Campaign Synchronization"
    ]
    assert len(synchronization_sections) == 1
    section_items = synchronization_sections[0].args[1]
    assert isinstance(section_items, ast.Name)
    assert section_items.id == "campaign_synchronization"


def test_entity_shortcuts_are_clearly_labelled_as_entities() -> None:
    """The expandable entity-only section must not imply broader workshop tools."""
    method = _create_sidebar_method()
    string_literals = {
        node.value for node in ast.walk(method) if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }

    assert "Campaign Entities" in string_literals
    assert "Campaign Workshop" not in string_literals
