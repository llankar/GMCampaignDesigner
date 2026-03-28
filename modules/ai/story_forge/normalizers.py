from __future__ import annotations

import json
import re
from typing import Any


def parse_json_strict_with_fallback(raw_text: str, *, fallback: dict[str, Any] | None = None) -> dict[str, Any]:
    """Parse strict JSON, then fallback to best-effort extraction."""

    if not raw_text:
        return dict(fallback or {})

    text = raw_text.strip()
    try:
        value = json.loads(text)
        if isinstance(value, dict):
            return value
    except Exception:
        pass

    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text, flags=re.IGNORECASE).strip()
        text = text.rstrip("`").strip()
        try:
            value = json.loads(text)
            if isinstance(value, dict):
                return value
        except Exception:
            pass

    first_brace = text.find("{")
    if first_brace >= 0:
        sliced = text[first_brace:]
        for end in range(len(sliced), max(len(sliced) - 4000, 0), -1):
            try:
                value = json.loads(sliced[:end])
                if isinstance(value, dict):
                    return value
            except Exception:
                continue

    return dict(fallback or {})


def normalize_rewrite_options(payload: dict[str, Any], *, brief: str) -> list[dict[str, str]]:
    options = payload.get("options") if isinstance(payload, dict) else None
    normalized: list[dict[str, str]] = []
    if isinstance(options, list):
        for idx, option in enumerate(options):
            if not isinstance(option, dict):
                continue
            title = str(option.get("title") or f"Scenario Option {idx + 1}").strip()
            summary = str(option.get("summary") or option.get("pitch") or brief).strip()
            pitch = str(option.get("pitch") or summary).strip()
            normalized.append({"title": title, "summary": summary, "pitch": pitch})
    if normalized:
        return normalized
    return [{"title": "Scenario Draft", "summary": brief.strip(), "pitch": brief.strip()}]


def normalize_entities(payload: dict[str, Any]) -> dict[str, list[str]]:
    defaults = {
        "NPCs": [],
        "Creatures": [],
        "Bases": [],
        "Places": [],
        "Maps": [],
        "Factions": [],
        "Objects": [],
    }
    entities = payload.get("entities") if isinstance(payload, dict) else None
    if not isinstance(entities, dict):
        return defaults
    for key in defaults:
        raw = entities.get(key) or []
        if isinstance(raw, str):
            raw = [raw]
        if isinstance(raw, list):
            defaults[key] = list(dict.fromkeys(str(item).strip() for item in raw if str(item).strip()))
    return defaults


def normalize_full_draft(payload: dict[str, Any], fallback_option: dict[str, str], fallback_entities: dict[str, list[str]]) -> dict[str, Any]:
    title = str(payload.get("title") or fallback_option.get("title") or "Scenario Draft").strip()
    summary = str(payload.get("summary") or fallback_option.get("summary") or "").strip()
    secrets = str(payload.get("secrets") or "").strip()

    scenes_raw = payload.get("scenes")
    scenes: list[dict[str, str]] = []
    if isinstance(scenes_raw, list):
        for idx, scene in enumerate(scenes_raw):
            if not isinstance(scene, dict):
                continue
            scene_title = str(scene.get("Title") or scene.get("title") or f"Scene {idx + 1}").strip()
            scene_summary = str(scene.get("Summary") or scene.get("summary") or "").strip()
            scene_type = str(scene.get("SceneType") or scene.get("type") or "Auto").strip()
            scenes.append({"Title": scene_title, "Summary": scene_summary, "Text": scene_summary, "SceneType": scene_type})

    if not scenes:
        scenes = [{"Title": "Scene 1", "Summary": summary, "Text": summary, "SceneType": "Setup"}]

    entities = normalize_entities(payload)
    for key, values in fallback_entities.items():
        if not entities.get(key):
            entities[key] = list(values)

    return {
        "title": title,
        "summary": summary,
        "secrets": secrets,
        "scenes": scenes,
        "entities": entities,
    }
