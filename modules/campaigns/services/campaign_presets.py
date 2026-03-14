from __future__ import annotations

import json
from pathlib import Path


PRESETS_DIR = Path(__file__).resolve().parent.parent / "presets"

FORM_KEYS = {"name", "genre", "tone", "status", "start_date", "end_date"}
TEXT_AREA_KEYS = {"logline", "setting", "main_objective", "stakes", "themes", "notes"}
ARC_KEYS = {"name", "summary", "objective", "status", "scenarios"}


def list_campaign_presets() -> list[dict]:
    """Return available campaign presets from modules/campaigns/presets/*.json."""

    if not PRESETS_DIR.exists():
        return []

    presets: list[dict] = []
    for path in sorted(PRESETS_DIR.glob("*.json"), key=lambda candidate: candidate.name.casefold()):
        preset = _load_preset_file(path)
        if preset:
            presets.append(preset)
    return presets


def _load_preset_file(path: Path) -> dict | None:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None

    if not isinstance(raw, dict):
        return None

    preset_id = str(raw.get("id") or path.stem).strip()
    if not preset_id:
        return None

    name = str(raw.get("name") or preset_id).strip()

    form_data = _extract_string_dict(raw.get("form"), FORM_KEYS)
    text_areas = _extract_string_dict(raw.get("text_areas"), TEXT_AREA_KEYS)
    arcs = _extract_arcs(raw.get("arcs"))

    return {
        "id": preset_id,
        "name": name,
        "description": str(raw.get("description") or "").strip(),
        "form": form_data,
        "text_areas": text_areas,
        "arcs": arcs,
    }


def _extract_string_dict(raw: object, allowed_keys: set[str]) -> dict[str, str]:
    if not isinstance(raw, dict):
        return {}
    result: dict[str, str] = {}
    for key in allowed_keys:
        value = raw.get(key)
        if value is None:
            continue
        result[key] = str(value).strip()
    return result


def _extract_arcs(raw: object) -> list[dict]:
    if not isinstance(raw, list):
        return []

    arcs: list[dict] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        arc: dict = {}
        for key in ARC_KEYS:
            if key not in item:
                continue
            if key == "scenarios":
                scenarios = item.get("scenarios")
                if isinstance(scenarios, list):
                    arc[key] = [str(entry).strip() for entry in scenarios if str(entry).strip()]
                else:
                    arc[key] = []
                continue
            arc[key] = str(item.get(key) or "").strip()
        if arc:
            if "status" not in arc:
                arc["status"] = "Planned"
            if "scenarios" not in arc:
                arc["scenarios"] = []
            arcs.append(arc)
    return arcs
