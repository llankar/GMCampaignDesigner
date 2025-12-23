from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Iterable, List, Optional

from modules.helpers.config_helper import ConfigHelper


def _extract_dict_value(value: dict) -> str:
    for key in ("path", "Path", "text", "Text", "value", "Value", "file", "File"):
        candidate = value.get(key)
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
    return ""


def _flatten_portrait_values(values: Iterable) -> List[str]:
    flattened: List[str] = []
    for entry in values:
        flattened.extend(parse_portrait_value(entry))
    return flattened


def parse_portrait_value(value) -> List[str]:
    if value is None:
        return []
    if isinstance(value, dict):
        extracted = _extract_dict_value(value)
        return [extracted] if extracted else []
    if isinstance(value, (list, tuple, set)):
        return _flatten_portrait_values(value)
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return []
        if stripped.startswith("[") and stripped.endswith("]"):
            try:
                parsed = json.loads(stripped)
            except json.JSONDecodeError:
                parsed = None
            if parsed is not None:
                return _flatten_portrait_values(parsed)
        lines = [line.strip() for line in stripped.splitlines() if line.strip()]
        if len(lines) > 1:
            return lines
        for delimiter in (";", "|"):
            if delimiter in stripped:
                return [part.strip() for part in stripped.split(delimiter) if part.strip()]
        return [stripped]
    return [str(value)]


def serialize_portrait_value(values: Iterable[str]) -> str:
    paths = [str(value).strip() for value in values if str(value).strip()]
    return "\n".join(paths)


def primary_portrait(value) -> str:
    portraits = parse_portrait_value(value)
    return portraits[0] if portraits else ""


def resolve_portrait_candidate(path: str, campaign_dir: Optional[str] = None) -> Optional[str]:
    if not path:
        return None
    candidate = Path(path)
    if candidate.is_absolute() and candidate.exists():
        return str(candidate)
    base_dir = Path(campaign_dir or ConfigHelper.get_campaign_dir())
    resolved = base_dir / candidate
    if resolved.exists():
        return str(resolved)
    if candidate.exists():
        return str(candidate)
    return None


def resolve_portrait_path(value, campaign_dir: Optional[str] = None) -> Optional[str]:
    path = primary_portrait(value)
    return resolve_portrait_candidate(path, campaign_dir)


def portrait_menu_label(path: str, index: int) -> str:
    base = os.path.basename(str(path)) if path else ""
    if base:
        return f"{index}. {base}"
    return f"Portrait {index}"
