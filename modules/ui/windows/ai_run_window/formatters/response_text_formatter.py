from __future__ import annotations

import json
from typing import Any


def format_ai_response_for_humans(response_text: str | None) -> str:
    """Format AI response text into a human-friendly representation."""

    payload = (response_text or "").strip()
    if not payload:
        return ""

    parsed = _try_parse_json(payload)
    if parsed is None:
        return payload

    if isinstance(parsed, dict):
        campaign_like = _format_campaign_payload(parsed)
        if campaign_like:
            return campaign_like

    return json.dumps(parsed, indent=2, ensure_ascii=False)


def _try_parse_json(payload: str) -> Any | None:
    stripped = payload.strip()
    if not stripped:
        return None

    if stripped.startswith("```"):
        stripped = stripped.strip("`").strip()
        if stripped.lower().startswith("json"):
            stripped = stripped[4:].strip()

    if stripped and stripped[0] not in "[{":
        return None

    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        return None


def _format_campaign_payload(data: dict[str, Any]) -> str:
    title = _line_text(data.get("title"))
    summary = _line_text(data.get("summary"))
    secrets = _line_text(data.get("secrets"))
    scenes = data.get("scenes")

    if not title and not summary and not isinstance(scenes, list):
        return ""

    lines: list[str] = []
    if title:
        lines.append(f"Title: {title}")
    if summary:
        lines.append("")
        lines.append("Summary")
        lines.append("-------")
        lines.append(summary)
    if secrets:
        lines.append("")
        lines.append("Secrets")
        lines.append("-------")
        lines.append(secrets)

    if isinstance(scenes, list):
        lines.append("")
        lines.append("Scenes")
        lines.append("------")
        for idx, scene in enumerate(scenes, start=1):
            if isinstance(scene, dict):
                scene_title = _line_text(scene.get("Title")) or f"Scene {idx}"
                scene_type = _line_text(scene.get("SceneType"))
                scene_summary = _line_text(scene.get("Summary"))
                lines.append(f"{idx}. {scene_title}{f' ({scene_type})' if scene_type else ''}")
                if scene_summary:
                    lines.append(f"   {scene_summary}")
            else:
                lines.append(f"{idx}. {_line_text(scene) or 'Scene'}")

    return "\n".join(lines).strip()


def _line_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return " ".join(value.split())
    if isinstance(value, (int, float, bool)):
        return str(value)
    return ""
