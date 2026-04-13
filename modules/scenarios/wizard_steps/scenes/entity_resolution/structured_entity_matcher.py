"""Resolve structured scene items to campaign entities.

Business rule: only entities that already exist in the campaign DB are added.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

from modules.scenarios.wizard_steps.scenes.entity_resolution.db_indexes import normalise_entity_name
from modules.scenarios.wizard_steps.scenes.scene_structured_editor_fields import parse_multiline_items


SECTION_ENTITY_TARGETS = {
    "SceneNPCs": ("NPCs",),
    "SceneLocations": ("Places",),
    "SceneClues": ("Clues",),
    "SceneObstacles": ("Creatures", "NPCs"),
}

_TOKEN_SPLIT_RE = re.compile(r"[,\n;/(){}\[\]|:!?]+")
_SUB_TOKEN_RE = re.compile(r"\s+(?:and|or|with|vs\.?|versus|at|in|on|near|inside|outside)\s+", flags=re.IGNORECASE)


def _dedupe_preserve(values: Iterable[str]) -> list[str]:
    """Deduplicate values while preserving original order."""
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        key = text.casefold()
        if not text or key in seen:
            continue
        seen.add(key)
        out.append(text)
    return out


def _tokenize_structured_item(item: Any) -> list[str]:
    """Tokenize one structured scene item into useful match candidates."""
    text = str(item or "").strip()
    if not text:
        return []
    parts = [part.strip(" -–—•\t") for part in _TOKEN_SPLIT_RE.split(text) if part.strip()]
    tokens: list[str] = [text]
    for part in parts:
        tokens.append(part)
        tokens.extend(piece.strip() for piece in _SUB_TOKEN_RE.split(part) if piece.strip())
    return _dedupe_preserve(tokens)


def _match_token(token: str, entity_index: dict[str, dict[str, str]]) -> str | None:
    """Try exact match first, then normalised match for a token."""
    exact = (entity_index or {}).get("exact") or {}
    normalised = (entity_index or {}).get("normalised") or {}
    if token in exact:
        return exact[token]
    return normalised.get(normalise_entity_name(token))


def resolve_scene_entities_from_structured(
    scene_record: dict[str, Any],
    db_indexes: dict[str, dict[str, dict[str, str]]],
) -> dict[str, list[str]]:
    """Resolve scene entities from structured sections against campaign DB indexes."""
    resolved = {
        "NPCs": [],
        "Creatures": [],
        "Places": [],
        "Clues": [],
    }
    record = scene_record if isinstance(scene_record, dict) else {}
    indexes = db_indexes if isinstance(db_indexes, dict) else {}

    for section_name, target_fields in SECTION_ENTITY_TARGETS.items():
        raw_items = parse_multiline_items(record.get(section_name))
        if not raw_items:
            continue
        for raw_item in raw_items:
            for token in _tokenize_structured_item(raw_item):
                for target_field in target_fields:
                    matched = _match_token(token, indexes.get(target_field) or {})
                    if matched:
                        resolved[target_field].append(matched)
                        break

    return {field: _dedupe_preserve(values) for field, values in resolved.items()}
