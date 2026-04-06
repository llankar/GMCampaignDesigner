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


def test_list_manageable_entities_excludes_internal_entity_types(monkeypatch):
    """Verify internal entity slugs are filtered from user-manageable lists."""
    defs = {
        "events": {"label": "Events"},
        "image_assets": {"label": "Image Assets"},
        "npcs": {"label": "NPCs"},
    }
    monkeypatch.setattr(template_loader, "load_entity_definitions", lambda: defs)

    assert template_loader.list_manageable_entities() == ["npcs"]


def test_list_known_entities_keeps_internal_entity_types(monkeypatch):
    """Verify internal slugs remain available for internal workflows."""
    defs = {
        "events": {"label": "Events"},
        "image_assets": {"label": "Image Assets"},
        "npcs": {"label": "NPCs"},
    }
    monkeypatch.setattr(template_loader, "load_entity_definitions", lambda: defs)

    assert "image_assets" in template_loader.list_known_entities()
