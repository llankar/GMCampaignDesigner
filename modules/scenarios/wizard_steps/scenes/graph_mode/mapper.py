"""Mapping helpers between scene payloads and UI text."""
from __future__ import annotations


def scenes_to_node_lines(scenes: list[dict]) -> list[str]:
    lines: list[str] = []
    for index, scene in enumerate(scenes, start=1):
        marker = "🎯" if index == 1 else "💬"
        lines.append(f"{marker} {index}. {scene.get('title')}")
        if scene.get("objective"):
            lines.append(f"   └─ objectif: {scene['objective']}")
        if index < len(scenes):
            lines.append(f"   └─ ensuite → {index + 1}")
    return lines
