"""Normalize AI-generated scenario payloads into editable scenario fields."""

from __future__ import annotations

import json
import re
from typing import Any

_ENTITY_FIELDS = (
    "NPCs",
    "Places",
    "Creatures",
    "Factions",
    "Objects",
    "Maps",
    "Bases",
    "Villains",
)
_SECTION_ALIASES = {
    "title": "Title",
    "scenario title": "Title",
    "summary": "Summary",
    "scenario summary": "Summary",
    "scenario summary max 8 lines": "Summary",
    "scenario summary maximum 8 short lines": "Summary",
    "secrets": "Secrets",
    "secrets and twists": "Secrets",
    "twists": "Secrets",
    "npcs": "NPCs",
    "npc": "NPCs",
    "places": "Places",
    "locations": "Places",
    "location": "Places",
    "creatures": "Creatures",
    "factions": "Factions",
    "objects": "Objects",
    "maps": "Maps",
    "bases": "Bases",
    "villains": "Villains",
}
_SCENE_HEADING_RE = re.compile(
    r"^\s{0,3}(?:#{2,6}\s*)?(?:\*{1,2})?"
    r"(?:scene\s*)?(\d+)?\s*[:.)-]?\s*(.*?)"
    r"(?:\*{1,2})?\s*$",
    re.IGNORECASE,
)
_FIELD_RE = re.compile(
    r"^\s*(?:[-*]\s*)?(?:\*{1,2})?"
    r"([A-Za-z][A-Za-z0-9 (),/&-]{1,60})"
    r"(?:\*{1,2})?\s*:\s*(.*)$"
)
_MARKDOWN_HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s+(.+?)\s*$")


def normalize_generated_scenario_payload(raw: Any) -> dict[str, Any]:
    """Return a scenario dict with structured scenes and top-level entity links."""
    if isinstance(raw, dict):
        return _normalize_mapping(raw)
    return parse_markdown_scenario(str(raw or ""))


def parse_markdown_scenario(text: str) -> dict[str, Any]:
    """Parse common markdown/plain-text scenario output into scenario fields."""
    text = str(text or "").strip()
    result: dict[str, Any] = {"Title": "", "Summary": text, "Secrets": "", "Scenes": []}
    if not text:
        return result

    json_entities, scenario_text = _extract_json_entity_sections(text)
    before_scenes, scene_blocks = _split_scene_blocks(scenario_text)
    sections = _extract_sections(before_scenes)

    title = sections.get("Title") or _extract_inline_field(before_scenes, "title")
    if title:
        result["Title"] = _clean_value(title)

    summary = sections.get("Summary")
    if summary:
        result["Summary"] = summary.strip()
    elif before_scenes.strip():
        result["Summary"] = _strip_known_inline_fields(before_scenes).strip() or text

    secrets = sections.get("Secrets")
    if secrets:
        result["Secrets"] = secrets.strip()

    for key in _ENTITY_FIELDS:
        values = _coerce_names(sections.get(key))
        if values:
            result[key] = values

    for key, records in json_entities.items():
        if records:
            result[key] = records

    scenes = [_parse_scene_block(title_part, body) for title_part, body in scene_blocks]
    scenes = [scene for scene in scenes if scene.get("Title") or _scene_text(scene)]
    if scenes:
        result["Scenes"] = scenes
        _promote_scene_entities(result, scenes)
    return result


def _normalize_mapping(data: dict[str, Any]) -> dict[str, Any]:
    result = dict(data)
    scenes = result.get("Scenes") or []
    if isinstance(scenes, dict) and isinstance(scenes.get("Scenes"), list):
        scenes = scenes["Scenes"]
    if isinstance(scenes, (str, bytes)):
        parsed = parse_markdown_scenario(str(scenes))
        scenes = parsed.get("Scenes") or [{"Text": str(scenes)}]
    if not isinstance(scenes, list):
        scenes = [scenes]
    normalized_scenes = [
        _normalize_scene(scene, idx) for idx, scene in enumerate(scenes, start=1)
    ]
    result["Scenes"] = normalized_scenes
    _promote_scene_entities(result, normalized_scenes)
    return result


def _normalize_scene(scene: Any, index: int) -> dict[str, Any]:
    if isinstance(scene, dict):
        normalized = dict(scene)
        if "Text" not in normalized:
            for key in ("Summary", "Description", "Gist", "Purpose"):
                if normalized.get(key):
                    normalized["Text"] = normalized[key]
                    break
        for key in _ENTITY_FIELDS:
            if key in normalized:
                normalized[key] = _coerce_names(normalized.get(key))
        return normalized
    parsed = _parse_scene_block(f"Scene {index}", str(scene or ""))
    return parsed


_JSON_ENTITY_HEADING_RE = re.compile(
    r"^\s{0,3}(?:"
    r"#{1,6}\s+(?P<markdown>NPCs?|Locations?|Places?)\s*(?:\([^)]*json[^)]*\))?"
    r"|\*\*(?P<bold_colon>NPCs?|Locations?|Places?)\s*:\*\*"
    r"|\*\*(?P<bold>NPCs?|Locations?|Places?)\*\*\s*:"
    r")\s*$",
    re.IGNORECASE,
)
_JSON_FENCE_RE = re.compile(r"^\s*```(?:json)?\s*$", re.IGNORECASE)
_FENCE_END_RE = re.compile(r"^\s*```\s*$")


def _extract_json_entity_sections(text: str) -> tuple[dict[str, list[dict[str, Any]]], str]:
    """Extract fenced NPC/place JSON blocks and remove them from scene prose."""
    entities: dict[str, list[dict[str, Any]]] = {"NPCs": [], "Places": []}
    lines = text.splitlines()
    keep = [True] * len(lines)
    index = 0
    while index < len(lines):
        heading = _JSON_ENTITY_HEADING_RE.match(lines[index])
        if not heading:
            index += 1
            continue
        entity_label = next(group for group in heading.groups() if group)
        canonical = "NPCs" if entity_label.lower().startswith("npc") else "Places"
        cursor = index + 1
        while cursor < len(lines) and not lines[cursor].strip():
            cursor += 1
        if cursor >= len(lines) or not _JSON_FENCE_RE.match(lines[cursor]):
            index += 1
            continue
        end = cursor + 1
        while end < len(lines) and not _FENCE_END_RE.match(lines[end]):
            end += 1
        if end >= len(lines):
            index += 1
            continue
        raw_json = "\n".join(lines[cursor + 1 : end]).strip()
        records = _parse_entity_json_records(raw_json)
        if records:
            entities[canonical].extend(records)
            for remove_index in range(index, end + 1):
                keep[remove_index] = False
            index = end + 1
            continue
        index += 1
    cleaned_text = "\n".join(line for line, should_keep in zip(lines, keep) if should_keep).strip()
    return {key: _dedupe_entity_records(value) for key, value in entities.items()}, cleaned_text


def _parse_entity_json_records(raw_json: str) -> list[dict[str, Any]]:
    try:
        parsed = json.loads(raw_json)
    except json.JSONDecodeError:
        return []
    if isinstance(parsed, dict):
        parsed = [parsed]
    if not isinstance(parsed, list):
        return []
    records: list[dict[str, Any]] = []
    for item in parsed:
        if not isinstance(item, dict):
            continue
        name = item.get("Name") or item.get("Title") or item.get("name") or item.get("title")
        if not str(name or "").strip():
            continue
        record = {str(key): value for key, value in item.items()}
        if not record.get("Name"):
            record["Name"] = str(name).strip()
        records.append(record)
    return records


def _dedupe_entity_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for record in records:
        name = str(record.get("Name") or record.get("Title") or "").strip()
        key = name.casefold()
        if not name or key in seen:
            continue
        seen.add(key)
        deduped.append(record)
    return deduped


def _split_scene_blocks(text: str) -> tuple[str, list[tuple[str, str]]]:
    lines = text.splitlines()
    scene_indices: list[tuple[int, str]] = []
    for i, line in enumerate(lines):
        match = _SCENE_HEADING_RE.match(line)
        line_label = line.lower().lstrip("# ").strip()
        if match and (match.group(1) or line_label.startswith("scene ")):
            title = (
                match.group(2).strip()
                or f"Scene {match.group(1) or len(scene_indices)+1}"
            )
            scene_indices.append((i, title))
    if not scene_indices:
        return text, []
    before = "\n".join(lines[: scene_indices[0][0]])
    blocks = []
    for pos, (start, title) in enumerate(scene_indices):
        end = scene_indices[pos + 1][0] if pos + 1 < len(scene_indices) else len(lines)
        blocks.append((title, "\n".join(lines[start + 1 : end]).strip()))
    return before, blocks


def _extract_sections(text: str) -> dict[str, str]:
    sections: dict[str, list[str]] = {}
    current: str | None = None
    for line in text.splitlines():
        heading = _MARKDOWN_HEADING_RE.match(line)
        field = _FIELD_RE.match(line)
        key = None
        rest = ""
        if heading:
            key = _canonical_key(heading.group(1))
        elif field:
            key = _canonical_key(field.group(1))
            rest = field.group(2).strip()
        if heading or field:
            if key:
                current = key
                sections.setdefault(current, [])
                if rest:
                    sections[current].append(rest)
                continue
            current = None
            continue
        if current:
            sections[current].append(line)
    return {key: _clean_value("\n".join(lines)) for key, lines in sections.items()}


def _parse_scene_block(title: str, body: str) -> dict[str, Any]:
    scene: dict[str, Any] = {"Title": _clean_value(title), "Text": ""}
    text_lines: list[str] = []
    for line in str(body or "").splitlines():
        field = _FIELD_RE.match(line)
        if field:
            key = _canonical_key(field.group(1))
            value = _clean_value(field.group(2))
            if key in _ENTITY_FIELDS:
                scene[key] = _coerce_names(value)
                continue
            if key == "Places":
                scene["Places"] = _coerce_names(value)
                continue
            if key in {"Summary", "Secrets"} or field.group(1).strip().lower() in {
                "purpose",
                "atouts",
                "stakes",
            }:
                if value:
                    text_lines.append(f"{field.group(1).strip()}: {value}")
                continue
        text_lines.append(line)
    scene["Text"] = _clean_value("\n".join(text_lines))
    return scene


def _promote_scene_entities(
    result: dict[str, Any], scenes: list[dict[str, Any]]
) -> None:
    for key in _ENTITY_FIELDS:
        existing_value = result.get(key)
        combined_records = _entity_records_from_value(existing_value)
        combined_names = _coerce_names(existing_value)
        for scene in scenes:
            for name in _coerce_names(scene.get(key)):
                if name not in combined_names:
                    combined_names.append(name)
                    if combined_records:
                        combined_records.append({"Name": name})
        if combined_records:
            result[key] = _dedupe_entity_records(combined_records)
        elif combined_names:
            result[key] = combined_names


def _entity_records_from_value(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, dict):
        return _parse_entity_json_records(json.dumps(value))
    if not isinstance(value, list) or not any(isinstance(item, dict) for item in value):
        return []
    records: list[dict[str, Any]] = []
    for item in value:
        if isinstance(item, dict):
            records.extend(_parse_entity_json_records(json.dumps(item)))
        else:
            name = str(item or "").strip()
            if name:
                records.append({"Name": name})
    return _dedupe_entity_records(records)


def _canonical_key(label: str) -> str | None:
    normalized = re.sub(r"[^a-z0-9]+", " ", str(label).lower()).strip()
    return _SECTION_ALIASES.get(normalized)


def _coerce_names(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        values: list[str] = []
        for item in value:
            values.extend(_coerce_names(item))
        return _dedupe(values)
    if isinstance(value, dict):
        return _coerce_names(
            value.get("Name")
            or value.get("Title")
            or value.get("name")
            or value.get("title")
        )
    text = _clean_value(str(value))
    lines = [line.strip(" -*•") for line in text.splitlines() if line.strip(" -*•")]
    if len(lines) > 1:
        return _dedupe(lines)
    parts = re.split(r";|\band\b|&", text)
    return _dedupe(part.strip(" -*•") for part in parts if part.strip(" -*•"))


def _dedupe(values) -> list[str]:
    result: list[str] = []
    for value in values:
        text = str(value).strip()
        if text and text not in result:
            result.append(text)
    return result


def _clean_value(value: Any) -> str:
    return re.sub(r"^[-*•\s]+", "", str(value or "").replace("**", "")).strip()


def _extract_inline_field(text: str, field_name: str) -> str:
    match = re.search(
        rf"^\s*(?:\*\*)?{re.escape(field_name)}(?:\*\*)?\s*:\s*(.+)$",
        text,
        re.IGNORECASE | re.MULTILINE,
    )
    return match.group(1).strip() if match else ""


def _strip_known_inline_fields(text: str) -> str:
    return re.sub(
        r"^\s*(?:\*\*)?(?:Title|Scenario Title)(?:\*\*)?\s*:.+$",
        "",
        text,
        flags=re.IGNORECASE | re.MULTILINE,
    )


def _scene_text(scene: dict[str, Any]) -> str:
    text = scene.get("Text", "")
    if isinstance(text, dict):
        return str(text.get("text", ""))
    return str(text or "")
