"""Normalize AI-generated scenario payloads into editable scenario fields."""

from __future__ import annotations

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
    r"^\s{0,3}#{2,6}\s*(?:scene\s*)?(\d+)?\s*[:.)-]?\s*(.*)$", re.IGNORECASE
)
_FIELD_RE = re.compile(
    r"^\s*(?:[-*]\s*)?(?:\*\*)?([A-Za-z][A-Za-z0-9 (),/&-]{1,60})(?:\*\*)?\s*:\s*(.*)$"
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

    before_scenes, scene_blocks = _split_scene_blocks(text)
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
        combined = _coerce_names(result.get(key))
        for scene in scenes:
            for name in _coerce_names(scene.get(key)):
                if name not in combined:
                    combined.append(name)
        if combined:
            result[key] = combined


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
