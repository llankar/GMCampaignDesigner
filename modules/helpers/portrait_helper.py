"""Utilities for portrait helper."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Iterable, List, Optional

from modules.helpers.config_helper import ConfigHelper


def _extract_dict_value(value: dict) -> str:
    """Extract dict value."""
    for key in ("path", "Path", "text", "Text", "value", "Value", "file", "File"):
        # Process each key while updating dict value.
        candidate = value.get(key)
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
    return ""


def _flatten_portrait_values(values: Iterable) -> List[str]:
    """Internal helper for flatten portrait values."""
    flattened: List[str] = []
    for entry in values:
        flattened.extend(parse_portrait_value(entry))
    return flattened


def parse_portrait_value(value) -> List[str]:
    """Parse portrait value."""
    if value is None:
        return []
    if isinstance(value, dict):
        extracted = _extract_dict_value(value)
        return [extracted] if extracted else []
    if isinstance(value, (list, tuple, set)):
        return _flatten_portrait_values(value)
    if isinstance(value, str):
        # Handle the branch where isinstance(value, str).
        stripped = value.strip()
        if not stripped:
            return []
        if stripped.startswith("[") and stripped.endswith("]"):
            # Handle the branch where stripped.startswith('[') and stripped.endswith(']').
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
    """Serialize portrait value."""
    paths = [str(value).strip() for value in values if str(value).strip()]
    return "\n".join(paths)


def primary_portrait(value) -> str:
    """Handle primary portrait."""
    portraits = parse_portrait_value(value)
    return portraits[0] if portraits else ""


def normalize_portrait_path(path: str) -> str:
    """Normalize portrait path."""
    return str(path or "").strip().replace("\\", "/")


def resolve_portrait_candidate(path: str, campaign_dir: Optional[str] = None) -> Optional[str]:
    """Resolve portrait candidate."""
    if not path:
        return None
    base_dir = Path(campaign_dir or ConfigHelper.get_campaign_dir())

    candidate = Path(path)
    normalized_path = normalize_portrait_path(path)
    normalized_candidate = Path(normalized_path) if normalized_path else None

    candidate_variants = []

    if candidate.is_absolute():
        candidate_variants.append(candidate)
    if normalized_candidate and normalized_candidate.is_absolute():
        candidate_variants.append(normalized_candidate)

    if normalized_candidate and not normalized_candidate.is_absolute():
        candidate_variants.append(base_dir / normalized_candidate)
    if not candidate.is_absolute():
        candidate_variants.append(base_dir / candidate)

    candidate_variants.append(candidate)
    if normalized_candidate is not None:
        candidate_variants.append(normalized_candidate)

    seen = set()
    for variant in candidate_variants:
        # Process each variant from candidate_variants.
        variant_key = str(variant)
        if not variant_key or variant_key in seen:
            continue
        seen.add(variant_key)
        if variant.exists():
            return str(variant)
    return None


def resolve_portrait_path(value, campaign_dir: Optional[str] = None) -> Optional[str]:
    """Resolve portrait path."""
    path = primary_portrait(value)
    return resolve_portrait_candidate(path, campaign_dir)


def portrait_menu_label(path: str, index: int) -> str:
    """Handle portrait menu label."""
    base = os.path.basename(str(path)) if path else ""
    if base:
        return f"{index}. {base}"
    return f"Portrait {index}"
