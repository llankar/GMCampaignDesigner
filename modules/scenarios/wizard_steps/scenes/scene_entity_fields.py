SCENE_ENTITY_FIELDS = ("NPCs", "Creatures", "Bases", "Places", "Maps")


def normalise_entity_list(value):
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
        key = item.casefold()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped
