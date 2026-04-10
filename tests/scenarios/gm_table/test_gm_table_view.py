"""Targeted tests for GM Table entity panels."""

from __future__ import annotations

from types import SimpleNamespace

import modules.generic.entity_detail_factory as entity_detail_factory
import modules.scenarios.gm_table_view as gm_table_view_module
from modules.scenarios.gm_table.workspace import resolve_default_panel_size
from modules.scenarios.gm_table_view import GMTableView


def test_resolve_default_panel_size_prefers_large_scenario_panels() -> None:
    """Scenario panels should open larger than generic entity panels."""
    scenario_size = resolve_default_panel_size("entity", {"entity_type": "Scenarios"})
    npc_size = resolve_default_panel_size("entity", {"entity_type": "NPCs"})

    assert scenario_size == (920, 680)
    assert scenario_size[0] > npc_size[0]
    assert scenario_size[1] > npc_size[1]


def test_load_entity_item_accepts_title_or_name_case_insensitively() -> None:
    """Scenario lookups should work with legacy Name-only records too."""
    view = GMTableView.__new__(GMTableView)
    view.wrappers = {
        "Scenarios": SimpleNamespace(
            load_items=lambda: [
                {"Title": "Night Run"},
                {"Name": "Legacy Case"},
            ]
        )
    }

    titled = GMTableView._load_entity_item(view, "Scenarios", "night run")
    legacy = GMTableView._load_entity_item(view, "Scenarios", "legacy case")

    assert titled["Title"] == "Night Run"
    assert legacy["Name"] == "Legacy Case"


def test_open_entity_panel_only_grows_existing_panel_when_needed() -> None:
    """Reopening an entity should preserve a readable user-sized panel."""
    captured = []
    workspace = SimpleNamespace(
        serialize=lambda: {
            "panels": [
                {
                    "panel_id": "panel-42",
                    "kind": "entity",
                    "state": {
                        "entity_type": "Scenarios",
                        "entity_name": "Night Run",
                    },
                }
            ]
        },
        bring_to_front=lambda panel_id: captured.append(("front", panel_id)),
        ensure_panel_minimum_size=lambda panel_id, width, height: captured.append(
            ("ensure", panel_id, width, height)
        ),
    )
    view = GMTableView.__new__(GMTableView)
    view.workspace = workspace
    view._load_entity_item = lambda _entity_type, _name: {"Title": "Night Run"}
    view._preferred_entity_geometry = lambda _entity_type: {"width": 920, "height": 680}

    GMTableView.open_entity_panel(view, "Scenarios", "Night Run")

    assert captured == [
        ("front", "panel-42"),
        ("ensure", "panel-42", 920, 680),
    ]


def test_open_entity_panel_reuses_information_panel_with_title_canonicalization() -> None:
    """Informations panels should dedupe across Title/Name aliases."""
    captured = []
    workspace = SimpleNamespace(
        serialize=lambda: {
            "panels": [
                {
                    "panel_id": "panel-info",
                    "kind": "entity",
                    "state": {
                        "entity_type": "Informations",
                        "entity_name": "Secret Dossier",
                    },
                }
            ]
        },
        bring_to_front=lambda panel_id: captured.append(("front", panel_id)),
        ensure_panel_minimum_size=lambda panel_id, width, height: captured.append(
            ("ensure", panel_id, width, height)
        ),
    )
    view = GMTableView.__new__(GMTableView)
    view.workspace = workspace
    view._load_entity_item = lambda _entity_type, _name: {
        "Title": "Secret Dossier",
        "Name": "Old Note",
    }
    view._preferred_entity_geometry = lambda _entity_type: {"width": 760, "height": 580}
    view._create_panel = lambda *args, **kwargs: captured.append(("create", args, kwargs))

    GMTableView.open_entity_panel(view, "Informations", "Old Note")

    assert captured == [
        ("front", "panel-info"),
        ("ensure", "panel-info", 760, 580),
    ]


def test_open_entity_panel_uses_useful_geometry_for_new_scenario_panel() -> None:
    """Fresh scenario panels should be created at a readable size."""
    captured = {}
    view = GMTableView.__new__(GMTableView)
    view.workspace = SimpleNamespace()
    view._find_existing_entity_panel = lambda _entity_type, _name, **_kwargs: None
    view._load_entity_item = lambda _entity_type, _name: {"Name": "Legacy Case"}
    view._preferred_entity_geometry = lambda _entity_type: {"width": 920, "height": 680}

    def _capture(kind, title, state, *, geometry=None):
        captured["kind"] = kind
        captured["title"] = title
        captured["state"] = state
        captured["geometry"] = geometry
        return "panel-new"

    view._create_panel = _capture

    GMTableView.open_entity_panel(view, "Scenarios", "Legacy Case")

    assert captured["kind"] == "entity"
    assert captured["title"] == "Scenario: Legacy Case"
    assert captured["state"] == {
        "entity_type": "Scenarios",
        "entity_name": "Legacy Case",
    }
    assert captured["geometry"] == {"width": 920, "height": 680}


def test_build_entity_content_calls_detail_factory(monkeypatch) -> None:
    """Entity content should be built through the shared detail factory."""
    captured = {}

    class _DummyFrame:
        def grid(self, **kwargs):
            captured["grid"] = kwargs

    def _fake_factory(entity_type, item, *, master, open_entity_callback):
        captured["entity_type"] = entity_type
        captured["item"] = item
        captured["master"] = master
        captured["callback"] = open_entity_callback
        return _DummyFrame()

    view = GMTableView.__new__(GMTableView)
    expected_item = {"Title": "Night Run"}
    view._load_entity_item = lambda _entity_type, _name: expected_item
    callback = lambda *args, **kwargs: None
    view.open_entity_panel = callback
    host = object()

    monkeypatch.setattr(gm_table_view_module, "create_entity_detail_frame", _fake_factory)

    frame = GMTableView._build_entity_content(
        view,
        host,
        {"entity_type": "Scenarios", "entity_name": "Night Run"},
    )

    assert isinstance(frame, _DummyFrame)
    assert captured["entity_type"] == "Scenarios"
    assert captured["item"] is expected_item
    assert captured["master"] is host
    assert captured["callback"] is callback
    assert captured["grid"] == {"row": 0, "column": 0, "sticky": "nsew"}


def test_context_menu_handler_resolution_is_safe_without_gm_screen_api() -> None:
    """GM Table hosts without a context-menu API should not crash the detail factory."""

    class _HostWithoutMenu:
        pass

    class _HostWithMenu:
        def _show_context_menu(self, _event):
            return None

    assert entity_detail_factory._resolve_context_menu_handler(_HostWithoutMenu()) is None
    assert callable(entity_detail_factory._resolve_context_menu_handler(_HostWithMenu()))


def test_context_menu_binding_helpers_skip_hosts_without_menu_api(monkeypatch) -> None:
    """Context-menu binding should be a no-op for GM Table style hosts."""

    class _DummyWidget:
        def __init__(self) -> None:
            self.bind_calls = []

        def bind(self, sequence, callback) -> None:
            self.bind_calls.append((sequence, callback))

    class _HostWithMenu:
        def _show_context_menu(self, _event):
            return None

    recursive_calls = []
    widget = _DummyWidget()

    monkeypatch.setattr(
        entity_detail_factory,
        "bind_context_menu_recursively",
        lambda target, callback: recursive_calls.append((target, callback)),
    )

    assert entity_detail_factory._bind_host_context_menu(widget, object()) is None
    assert widget.bind_calls == []

    assert entity_detail_factory._bind_host_context_menu_recursively(widget, object()) is None
    assert recursive_calls == []

    handler = entity_detail_factory._bind_host_context_menu(widget, _HostWithMenu())
    assert callable(handler)
    assert widget.bind_calls[-2][0] == "<Button-3>"
    assert widget.bind_calls[-1][0] == "<Control-Button-1>"

    recursive_handler = entity_detail_factory._bind_host_context_menu_recursively(
        widget,
        _HostWithMenu(),
    )
    assert callable(recursive_handler)
    assert recursive_calls[-1][0] is widget
