"""Shared helpers for scene structured field editors."""

from modules.scenarios.scene_structured_fields import (
    SCENE_STRUCTURED_SECTION_FIELDS,
    migrate_scene_to_structured_fields,
)


SCENE_STRUCTURED_FIELD_LABELS = {
    section["field"]: section["title"] for section in SCENE_STRUCTURED_SECTION_FIELDS
}


def parse_multiline_items(raw_value):
    """Convert multiline/bulleted text into a clean string list."""
    if isinstance(raw_value, (list, tuple, set)):
        values = []
        for item in raw_value:
            values.extend(parse_multiline_items(item))
        return values
    text = str(raw_value or "")
    cleaned = []
    seen = set()
    for line in text.splitlines():
        item = line.strip()
        if not item:
            continue
        if item.startswith("-"):
            item = item[1:].strip()
        key = item.casefold()
        if not item or key in seen:
            continue
        seen.add(key)
        cleaned.append(item)
    return cleaned


def convert_structured_fields_from_text(scene_payload, body_text):
    """Run the legacy parser once and return structured scene fields."""
    migrated = migrate_scene_to_structured_fields(scene_payload, body_text or "")
    return {
        section["field"]: parse_multiline_items(migrated.get(section["field"]))
        for section in SCENE_STRUCTURED_SECTION_FIELDS
    }
