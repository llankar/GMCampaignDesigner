"""Validation helpers for graph mode scenes."""
from __future__ import annotations


def validate_scenes(scenes: list[dict]) -> list[str]:
    issues: list[str] = []
    for index, scene in enumerate(scenes, start=1):
        if not str(scene.get("title") or "").strip():
            issues.append(f"Scene {index} has an empty title")
    return issues
