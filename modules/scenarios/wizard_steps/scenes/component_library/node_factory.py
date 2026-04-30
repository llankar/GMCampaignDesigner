from __future__ import annotations

import re


def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-") or "scene"


def normalise_flow_node_id(title, existing_ids):
    used = {str(value).strip() for value in (existing_ids or []) if str(value).strip()}
    base = _slugify(str(title or "Scene"))
    candidate = base
    idx = 2
    while candidate in used:
        candidate = f"{base}-{idx}"
        idx += 1
    return candidate


def build_default_node(kind: str, x: int, y: int, existing_ids=None, scene_index: int = 0):
    safe_kind = str(kind or "scene").strip() or "scene"
    title = " ".join(part.capitalize() for part in safe_kind.split("_"))
    node_id = normalise_flow_node_id(safe_kind, existing_ids or [])
    return {
        "id": node_id,
        "title": title,
        "scene_index": int(scene_index),
        "x": int(x),
        "y": int(y),
        "kind": safe_kind,
        "summary": "",
        "scene_fields": {"SceneType": "", "structured": {}, "entities": {}},
    }
