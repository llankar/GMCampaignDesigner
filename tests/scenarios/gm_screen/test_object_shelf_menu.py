"""Tests for the GM Screen object shelf launcher."""

from __future__ import annotations

import modules.scenarios.gm_screen_view as gm_screen_module
from modules.scenarios.gm_screen_view import GMScreenView


def test_add_menu_options_include_object_shelf_static() -> None:
    """GM Screen add-menu declaration should expose the shared object shelf."""
    options_source = GMScreenView.__init__.__code__.co_consts

    assert "Object Shelf" in options_source


def test_restore_tab_from_config_supports_object_shelf() -> None:
    """Saved GM Screen layouts should restore object shelf tabs by kind."""
    captured = []
    view = GMScreenView.__new__(GMScreenView)
    view.open_object_shelf_tab = lambda title=None: captured.append(title)

    GMScreenView._restore_tab_from_config(
        view, {"kind": "object_shelf", "title": "Object Shelf"}
    )

    assert captured == ["Object Shelf"]


def test_open_object_shelf_tab_uses_shared_builder(monkeypatch) -> None:
    """Object shelf tabs should use the shared panel factory and layout metadata."""
    created = []
    added = {}

    def _fake_create(master, open_entity_callback=None):
        created.append((master, open_entity_callback))
        return {"master": master}

    monkeypatch.setattr(gm_screen_module, "create_object_shelf_panel", _fake_create)

    view = GMScreenView.__new__(GMScreenView)
    view.content_area = "content-area"
    view.open_entity_tab = object()
    view.add_tab = lambda name, content_frame, content_factory=None, layout_meta=None: added.update(
        {
            "name": name,
            "content_frame": content_frame,
            "content_factory": content_factory,
            "layout_meta": layout_meta,
        }
    )

    GMScreenView.open_object_shelf_tab(view, title="Objects")
    built = added["content_factory"]("factory-host")

    assert created == [
        ("content-area", view.open_entity_tab),
        ("factory-host", view.open_entity_tab),
    ]
    assert added["name"] == "Objects"
    assert added["content_frame"] == {"master": "content-area"}
    assert built == {"master": "factory-host"}
    assert added["layout_meta"] == {"kind": "object_shelf"}


def test_add_menu_routing_opens_object_shelf_tab() -> None:
    """The GM Screen add-menu router should launch the object shelf."""
    captured = []
    view = GMScreenView.__new__(GMScreenView)
    view.open_object_shelf_tab = lambda: captured.append("opened")

    GMScreenView.open_selection_window(view, "Object Shelf")

    assert captured == ["opened"]


def test_object_shelf_panel_defaults_to_shelf_view_mode() -> None:
    """Shared Object Shelf hosts should expose shelf mode for canvas interactions."""
    module = __import__("modules.objects.object_shelf_panel", fromlist=["ObjectShelfPanel"])
    source_names = module.ObjectShelfPanel.__init__.__code__.co_names
    source_values = module.ObjectShelfPanel.__init__.__code__.co_consts

    assert "view_mode" in source_names
    assert "shelf" in source_values
