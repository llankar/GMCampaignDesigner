"""Helpers to aggregate linked entities from scenario scene payloads."""

from modules.scenarios.wizard_steps.scenes.scene_entity_fields import normalise_entity_list


def collect_scene_entity_names(scenes, field_name):
    """Return de-duplicated entity names for ``field_name`` across all scenes."""
    if not isinstance(scenes, list):
        return []

    names = []
    seen = set()
    for scene in scenes:
        if not isinstance(scene, dict):
            continue
        for name in normalise_entity_list(scene.get(field_name)):
            key = name.casefold()
            if key in seen:
                continue
            seen.add(key)
            names.append(name)
    return names
