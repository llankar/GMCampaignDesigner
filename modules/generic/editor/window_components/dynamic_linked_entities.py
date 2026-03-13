from __future__ import annotations

from modules.generic.editor.window_context import load_entities_list


ENTITY_CONFIG_BY_PLURAL = {
    "PCs": {"entity_type": "pcs", "singular": "PC"},
    "NPCs": {"entity_type": "npcs", "singular": "NPC"},
    "Villains": {"entity_type": "villains", "singular": "Villain"},
    "Places": {"entity_type": "places", "singular": "Place"},
    "Factions": {"entity_type": "factions", "singular": "Faction"},
    "Objects": {"entity_type": "objects", "singular": "Object"},
    "Creatures": {"entity_type": "creatures", "singular": "Creature"},
    "Books": {"entity_type": "books", "singular": "Book"},
    "Events": {"entity_type": "events", "singular": "Event"},
}


def resolve_linked_entity_source(field: dict) -> tuple[list[str], str]:
    """
    Resolve available options and action label for a dynamic combobox field.

    Supports both modern fields (linked_type) and legacy fields (name).
    """
    linked = (field.get("linked_type") or "").strip()
    fname = (field.get("name") or "").strip()
    key = linked or fname

    config = ENTITY_CONFIG_BY_PLURAL.get(key)
    if not config:
        return [], f"Add {fname}"

    options = load_entities_list(config["entity_type"])
    label = f"Add {linked or config['singular']}"
    return options, label

