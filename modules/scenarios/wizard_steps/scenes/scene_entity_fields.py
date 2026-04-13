"""Field helpers for scenes scene entity."""

SCENE_ENTITY_FIELDS = ("NPCs", "Creatures", "Clues", "Bases", "Places", "Maps")


def normalise_entity_list(value):
    """Handle normalise entity list."""
    if value is None:
        return []
    if isinstance(value, str):
        parts = [part.strip() for part in value.replace(";", ",").split(",")]
        return [part for part in parts if part]
    if isinstance(value, (list, tuple, set)):
        values = [str(item).strip() for item in value if str(item).strip()]
    else:
        values = [str(value).strip()]
    seen = set()
    deduped = []
    for item in values:
        # Process each item from values.
        key = item.casefold()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped
