"""Scene schema helpers for graph mode planner."""
from __future__ import annotations

from typing import Any

SCENE_DEFAULT_TITLE = "Objective principal"


def normalize_scene(scene: dict[str, Any], index: int) -> dict[str, Any]:
    normalized = dict(scene or {})
    normalized["title"] = str(normalized.get("title") or f"Scene {index}").strip()
    normalized["objective"] = str(normalized.get("objective") or "").strip()
    normalized["success_condition"] = str(normalized.get("success_condition") or "").strip()
    normalized["notes"] = str(normalized.get("notes") or "").strip()
    return normalized
