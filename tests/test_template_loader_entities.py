from modules.helpers import template_loader


def test_list_known_entity_labels_returns_sorted_display_labels(monkeypatch):
    defs = {
        "zeta": {"label": "Zeta"},
        "alpha": {"label": "Alpha"},
        "beta": {"label": "Beta"},
    }
    monkeypatch.setattr(template_loader, "load_entity_definitions", lambda: defs)

    assert template_loader.list_known_entity_labels() == ["Alpha", "Beta", "Zeta"]
