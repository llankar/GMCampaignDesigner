"""Regression tests for template loader entities."""

from modules.helpers import template_loader


def test_list_known_entity_labels_returns_sorted_display_labels(monkeypatch):
    """Verify that list known entity labels returns sorted display labels."""
    defs = {
        "zeta": {"label": "Zeta"},
        "alpha": {"label": "Alpha"},
        "beta": {"label": "Beta"},
    }
    monkeypatch.setattr(template_loader, "load_entity_definitions", lambda: defs)

    assert template_loader.list_known_entity_labels() == ["Alpha", "Beta", "Zeta"]


def test_list_manageable_entities_excludes_internal_slugs(monkeypatch):
    """Internal entities should not surface in generic management lists."""
    monkeypatch.setattr(
        template_loader,
        "list_known_entities",
        lambda: ["events", "image_assets", "maps", "npcs"],
    )

    assert template_loader.list_manageable_entities() == ["maps", "npcs"]


def test_list_manageable_entity_labels_excludes_internal_slugs(monkeypatch):
    """Manageable labels should omit internal entities."""
    monkeypatch.setattr(
        template_loader,
        "list_manageable_entities",
        lambda: ["maps", "npcs"],
    )
    monkeypatch.setattr(
        template_loader,
        "load_entity_definitions",
        lambda: {
            "events": {"label": "Events"},
            "image_assets": {"label": "Image Assets"},
            "maps": {"label": "Maps"},
            "npcs": {"label": "NPCs"},
        },
    )

    assert template_loader.list_manageable_entity_labels() == ["Maps", "NPCs"]
