"""Parsing helpers for campaign arc."""

from __future__ import annotations

import ast
import json
from typing import Any

from modules.campaigns.shared.arc_status import canonicalize_arc_status


def normalize_arc_status(arc: dict[str, Any]) -> dict[str, Any]:
    """Normalize arc status."""
    normalized = dict(arc)
    normalized["status"] = canonicalize_arc_status(normalized.get("status"))
    return normalized


def coerce_arc_list(raw_value: Any) -> list[dict[str, Any]]:
    """Coerce arc list."""
    def _from_dict(payload: dict[str, Any]) -> list[dict[str, Any]]:
        """Internal helper for from dict."""
        arcs_value = payload.get("arcs")
        if isinstance(arcs_value, list):
            return [normalize_arc_status(arc) for arc in arcs_value if isinstance(arc, dict)]

        text_value = payload.get("text")
        if text_value is not None:
            return coerce_arc_list(text_value)

        arc_keys = {"name", "summary", "objective", "status", "scenarios"}
        if any(key in payload for key in arc_keys):
            return [normalize_arc_status(payload)]

        return []

    if isinstance(raw_value, list):
        return [normalize_arc_status(arc) for arc in raw_value if isinstance(arc, dict)]

    if isinstance(raw_value, dict):
        return _from_dict(raw_value)

    if isinstance(raw_value, str):
        # Handle the branch where isinstance(raw_value, str).
        parsed: Any = None
        try:
            parsed = json.loads(raw_value)
        except Exception:
            try:
                parsed = ast.literal_eval(raw_value)
            except Exception:
                parsed = None

        if isinstance(parsed, list):
            return [normalize_arc_status(arc) for arc in parsed if isinstance(arc, dict)]
        if isinstance(parsed, dict):
            return _from_dict(parsed)

    return []
