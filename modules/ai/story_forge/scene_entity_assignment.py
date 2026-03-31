"""Assignment helpers for story forge scene entity."""
from __future__ import annotations

import re
from copy import deepcopy
from typing import Any

_SCENE_ENTITY_KEYS = ("NPCs", "Creatures", "Bases", "Places", "Maps", "Factions", "Objects")
_TOKEN_RE = re.compile(r"[a-z0-9]+")


def assign_unused_entities_to_scenes(
    scenes: list[dict[str, Any]], entities: dict[str, list[str]], *, include_diagnostics: bool = False
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Assign each top-level entity missing from scenes to the best candidate scene.

    The algorithm is deterministic and minimal:
    - entities already present in any scene are left untouched,
    - each unused entity is assigned to a single scene,
    - scene choice is based on keyword matching in title/summary with stable tie-breaking,
    - fallback uses first setup/investigation scene, otherwise first scene.
    """

    normalized_scenes = deepcopy(scenes)
    usage_map = _build_usage_map(normalized_scenes)

    fallback_scene_index = _select_fallback_scene_index(normalized_scenes)
    assignments: list[dict[str, Any]] = []

    for entity_type in _SCENE_ENTITY_KEYS:
        # Process each entity_type from _SCENE_ENTITY_KEYS.
        top_level_entities = entities.get(entity_type) or []
        if not isinstance(top_level_entities, list):
            continue

        for entity_name in top_level_entities:
            # Process each entity_name from top_level_entities.
            name = str(entity_name).strip()
            if not name:
                continue

            if name.casefold() in usage_map.get(entity_type, set()):
                continue

            target_scene_index, score = _find_best_scene_index(normalized_scenes, name, fallback_scene_index)
            target_scene = normalized_scenes[target_scene_index]

            raw_scene_entities = target_scene.get(entity_type)
            if not isinstance(raw_scene_entities, list):
                raw_scene_entities = []
            raw_scene_entities = list(raw_scene_entities)
            raw_scene_entities.append(name)
            target_scene[entity_type] = _dedupe_preserve_order(raw_scene_entities)

            usage_map.setdefault(entity_type, set()).add(name.casefold())
            assignments.append(
                {
                    "entity_type": entity_type,
                    "entity": name,
                    "scene_index": target_scene_index,
                    "scene_title": str(target_scene.get("Title") or ""),
                    "score": score,
                }
            )

    diagnostics = {
        "usage_map": {k: sorted(v) for k, v in usage_map.items()},
        "assignments": assignments,
        "fallback_scene_index": fallback_scene_index,
    }

    if not include_diagnostics:
        diagnostics = {"assignments": assignments}

    return normalized_scenes, diagnostics


def _build_usage_map(scenes: list[dict[str, Any]]) -> dict[str, set[str]]:
    """Build usage map."""
    usage_map: dict[str, set[str]] = {key: set() for key in _SCENE_ENTITY_KEYS}
    for scene in scenes:
        # Process each scene from scenes.
        if not isinstance(scene, dict):
            continue
        for entity_type in _SCENE_ENTITY_KEYS:
            # Process each entity_type from _SCENE_ENTITY_KEYS.
            raw_values = scene.get(entity_type)
            if not isinstance(raw_values, list):
                continue
            for raw in raw_values:
                # Process each raw from raw_values.
                value = str(raw).strip()
                if value:
                    usage_map[entity_type].add(value.casefold())
    return usage_map


def _find_best_scene_index(scenes: list[dict[str, Any]], entity_name: str, fallback_scene_index: int) -> tuple[int, int]:
    """Find best scene index."""
    best_index = fallback_scene_index
    best_score = -1

    for index, scene in enumerate(scenes):
        # Process each (index, scene) from enumerate(scenes).
        score = _score_scene(scene, entity_name)
        if score > best_score:
            best_score = score
            best_index = index

    if best_score <= 0:
        return fallback_scene_index, 0
    return best_index, best_score


def _score_scene(scene: dict[str, Any], entity_name: str) -> int:
    """Internal helper for score scene."""
    scene_text = " ".join(
        [
            str(scene.get("Title") or "").casefold(),
            str(scene.get("Summary") or "").casefold(),
            str(scene.get("Text") or "").casefold(),
        ]
    )
    entity_cf = entity_name.casefold()
    if not scene_text.strip():
        return 0

    score = 0
    if entity_cf in scene_text:
        score += 100

    keywords = [token for token in _TOKEN_RE.findall(entity_cf) if len(token) >= 3]
    unique_keywords = _dedupe_preserve_order(keywords)
    for keyword in unique_keywords:
        if keyword in scene_text:
            score += 10

    return score


def _select_fallback_scene_index(scenes: list[dict[str, Any]]) -> int:
    """Select fallback scene index."""
    for preferred in ("setup", "investigation"):
        for index, scene in enumerate(scenes):
            # Process each (index, scene) from enumerate(scenes).
            scene_type = str(scene.get("SceneType") or scene.get("type") or "").strip().casefold()
            if preferred in scene_type:
                return index
    return 0


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    """Internal helper for dedupe preserve order."""
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        # Process each value from values.
        key = str(value).strip().casefold()
        if not key or key in seen:
            continue
        seen.add(key)
        output.append(str(value).strip())
    return output
