"""Structured scene -> campaign entity resolution helpers."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable
from typing import Any

from modules.scenarios.wizard_steps.scenes.scene_structured_editor_fields import parse_multiline_items

SECTION_ENTITY_TARGETS = {
    "SceneNPCs": ("NPCs",),
    "SceneLocations": ("Places",),
    "SceneObstacles": ("Creatures", "NPCs"),
    "SceneClues": ("Clues",),
}

DB_ENTITY_TYPE_TO_WRAPPER_KEY = {
    "NPCs": "npcs",
    "Creatures": "creatures",
    "Places": "places",
    "Clues": "clues",
}

_LIGHT_PUNCTUATION_RE = re.compile(r"[\.,;:!?\"'`´’“”()\[\]{}_/\\|-]+")
_WORD_RE = re.compile(r"[a-z0-9]+")


def normalize_name(text: Any) -> str:
    """Normalize entity names for resilient matching."""
    raw = str(text or "").strip().lower()
    if not raw:
        return ""
    no_marks = "".join(
        char
        for char in unicodedata.normalize("NFKD", raw)
        if not unicodedata.combining(char)
    )
    simplified = _LIGHT_PUNCTUATION_RE.sub(" ", no_marks)
    return " ".join(simplified.split())


def _name_tokens(value: Any) -> tuple[str, ...]:
    return tuple(_WORD_RE.findall(normalize_name(value)))


def _dedupe_preserve(values: Iterable[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        if not text:
            continue
        key = text.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(text)
    return out


def _extract_entity_name(item: Any) -> str:
    if isinstance(item, dict):
        raw_name = item.get("Name") or item.get("Title")
    else:
        raw_name = item
    return str(raw_name or "").strip()


def build_campaign_entity_indexes(entity_wrappers: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Build exact and normalized indexes for campaign entities."""
    wrappers = entity_wrappers if isinstance(entity_wrappers, dict) else {}
    indexes: dict[str, dict[str, Any]] = {}

    for entity_field, wrapper_key in DB_ENTITY_TYPE_TO_WRAPPER_KEY.items():
        exact: dict[str, str] = {}
        normalized: dict[str, str] = {}
        tokenized: list[dict[str, Any]] = []
        wrapper = wrappers.get(wrapper_key)
        items: list[Any] = []
        if wrapper is not None:
            try:
                items = wrapper.load_items() or []
            except Exception:
                items = []

        for item in items:
            name = _extract_entity_name(item)
            if not name:
                continue
            exact.setdefault(name, name)
            normalized_name = normalize_name(name)
            normalized.setdefault(normalized_name, name)
            tokenized.append({
                "name": name,
                "tokens": frozenset(_name_tokens(name)),
            })

        indexes[entity_field] = {
            "exact": exact,
            "normalized": normalized,
            "tokenized": tokenized,
        }

    return indexes


def _edit_distance_leq_one(a: str, b: str) -> bool:
    if a == b:
        return True
    if abs(len(a) - len(b)) > 1:
        return False
    if len(a) > len(b):
        a, b = b, a

    i = j = edits = 0
    while i < len(a) and j < len(b):
        if a[i] == b[j]:
            i += 1
            j += 1
            continue
        edits += 1
        if edits > 1:
            return False
        if len(a) == len(b):
            i += 1
            j += 1
        else:
            j += 1

    if j < len(b) or i < len(a):
        edits += 1
    return edits <= 1


def _match_partial(candidate_tokens: frozenset[str], entity_index: dict[str, Any]) -> str | None:
    if not candidate_tokens:
        return None

    subset_candidates: list[tuple[str, int]] = []
    fuzzy_match: str | None = None

    tokenized_entries = list(entity_index.get("tokenized") or [])
    if not tokenized_entries:
        for name in (entity_index.get("exact") or {}).values():
            tokenized_entries.append({"name": name, "tokens": frozenset(_name_tokens(name))})

    for entry in tokenized_entries:
        entity_name = entry.get("name")
        entity_tokens = entry.get("tokens") or frozenset()
        if not entity_name or not entity_tokens:
            continue
        if entity_tokens.issubset(candidate_tokens):
            subset_candidates.append((entity_name, len(entity_tokens)))
            continue

        if len(entity_tokens) == 1:
            entity_token = next(iter(entity_tokens))
            if len(entity_token) < 6:
                continue
            for token in candidate_tokens:
                if len(token) < 6:
                    continue
                if _edit_distance_leq_one(token, entity_token):
                    if fuzzy_match and fuzzy_match != entity_name:
                        return None
                    fuzzy_match = entity_name
                    break

    if subset_candidates:
        subset_candidates.sort(key=lambda item: item[1], reverse=True)
        top_name, top_size = subset_candidates[0]
        competing = [name for name, size in subset_candidates if size == top_size and name != top_name]
        if not competing:
            return top_name
    return fuzzy_match


def _match_candidate(candidate: str, entity_index: dict[str, Any]) -> str | None:
    exact = entity_index.get("exact") or {}
    normalized = entity_index.get("normalized") or entity_index.get("normalised") or {}

    if candidate in exact:
        return exact[candidate]

    normalized_candidate = normalize_name(candidate)
    if normalized_candidate in normalized:
        return normalized[normalized_candidate]

    return _match_partial(frozenset(_name_tokens(candidate)), entity_index)


def resolve_entities_from_structured(scene: dict[str, Any], indexes: dict[str, dict[str, Any]]) -> dict[str, list[str]]:
    """Resolve scene entities from structured fields using campaign indexes."""
    resolved = {"NPCs": [], "Creatures": [], "Places": [], "Clues": []}
    record = scene if isinstance(scene, dict) else {}
    campaign_indexes = indexes if isinstance(indexes, dict) else {}

    for section, target_fields in SECTION_ENTITY_TARGETS.items():
        candidates = parse_multiline_items(record.get(section))
        if not candidates:
            continue
        for candidate in candidates:
            for target_field in target_fields:
                match = _match_candidate(str(candidate or "").strip(), campaign_indexes.get(target_field) or {})
                if match:
                    resolved[target_field].append(match)
                    break

    return {field: _dedupe_preserve(values) for field, values in resolved.items()}
