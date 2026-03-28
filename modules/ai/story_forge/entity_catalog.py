from __future__ import annotations

from modules.generic.generic_model_wrapper import GenericModelWrapper


ENTITY_TYPE_TO_FIELD = {
    "npcs": "NPCs",
    "creatures": "Creatures",
    "bases": "Bases",
    "places": "Places",
    "maps": "Maps",
    "factions": "Factions",
    "objects": "Objects",
    "villains": "Villains",
    "events": "Events",
    "books": "Books",
    "pcs": "PCs",
}


def load_db_entity_catalog(entity_types: tuple[str, ...] | None = None, limit: int = 100) -> dict[str, list[str]]:
    """Load existing entity names from DB wrappers to ground Story Forge output."""

    requested = entity_types or tuple(ENTITY_TYPE_TO_FIELD.keys())
    catalog: dict[str, list[str]] = {}
    for entity_type in requested:
        field_name = ENTITY_TYPE_TO_FIELD.get(entity_type)
        if not field_name:
            continue
        try:
            wrapper = GenericModelWrapper(entity_type)
            items = wrapper.load_items() or []
        except Exception:
            items = []
        names: list[str] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            name = str(item.get("Name") or item.get("Title") or item.get("name") or "").strip()
            if not name:
                continue
            names.append(name)
            if len(names) >= limit:
                break
        catalog[field_name] = list(dict.fromkeys(names))
    return catalog


def load_campaign_arc_context(campaign_context: dict | None = None, arc_context: dict | None = None) -> dict[str, str]:
    campaign_context = campaign_context or {}
    arc_context = arc_context or {}
    return {
        "campaign_name": str(campaign_context.get("name") or campaign_context.get("Name") or "").strip(),
        "campaign_summary": str(
            campaign_context.get("summary")
            or campaign_context.get("Summary")
            or campaign_context.get("logline")
            or ""
        ).strip(),
        "arc_name": str(arc_context.get("name") or arc_context.get("Name") or "").strip(),
        "arc_summary": str(arc_context.get("summary") or arc_context.get("Summary") or "").strip(),
        "arc_objective": str(arc_context.get("objective") or arc_context.get("Objective") or "").strip(),
        "arc_thread": str(arc_context.get("thread") or arc_context.get("Thread") or "").strip(),
    }
