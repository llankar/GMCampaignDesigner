from __future__ import annotations

from modules.scenarios.widgets.entity_chips import normalize_entity_payload


_PRIORITY_TAGS = {"boss", "important", "priority", "primary"}


def prepare_entities_for_group(entities):
    """Normalize and sort entity payloads for consistent rendering."""

    normalized_entities = []
    for index, entry in enumerate(entities or []):
        payload = normalize_entity_payload(entry)
        if not payload["name"]:
            continue

        metadata = _extract_metadata(entry)
        tags = _extract_tags(entry, metadata)
        priority_flag = _to_bool(metadata.get("boss")) or _to_bool(metadata.get("important"))
        if not priority_flag:
            priority_flag = any(tag in _PRIORITY_TAGS for tag in tags)

        importance = _extract_importance(entry, metadata)
        if not importance and priority_flag:
            importance = "Primary"

        payload.update(
            {
                "importance": importance,
                "_input_index": index,
                "_priority_flag": priority_flag,
                "_has_metadata": bool(metadata),
            }
        )
        normalized_entities.append(payload)

    normalized_entities.sort(key=_sort_key)
    return normalized_entities


def _sort_key(payload: dict):
    is_priority = payload.get("_priority_flag", False)
    has_metadata = payload.get("_has_metadata", False)
    order_index = int(payload.get("_input_index", 0))
    name = str(payload.get("name") or "").strip().lower()

    if has_metadata:
        return (0 if is_priority else 1, 0, name, order_index)
    return (0 if is_priority else 1, 1, order_index, name)


def _extract_metadata(entry) -> dict:
    if not isinstance(entry, dict):
        return {}
    metadata = entry.get("metadata")
    return metadata if isinstance(metadata, dict) else {}


def _extract_tags(entry, metadata: dict) -> set[str]:
    tags = []
    if isinstance(entry, dict):
        tags.extend(_coerce_list(entry.get("tags")))
    tags.extend(_coerce_list(metadata.get("tags")))

    normalized_tags = set()
    for tag in tags:
        tag_value = str(tag or "").strip().lower()
        if tag_value:
            normalized_tags.add(tag_value)
    return normalized_tags


def _extract_importance(entry, metadata: dict) -> str:
    raw_value = None
    if isinstance(entry, dict):
        raw_value = entry.get("importance") or entry.get("priority_level")
    if not raw_value:
        raw_value = metadata.get("importance") or metadata.get("priority") or metadata.get("priority_level")

    importance = str(raw_value or "").strip().lower()
    if importance in {"primary", "high", "main", "major"}:
        return "Primary"
    if importance in {"secondary", "low", "minor", "support"}:
        return "Secondary"
    return ""


def _coerce_list(value):
    if isinstance(value, (list, tuple, set)):
        return list(value)
    if value is None:
        return []
    return [value]


def _to_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}
    return False
