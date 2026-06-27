"""Persistence helpers for GM Table desk annotations."""

from __future__ import annotations

from typing import Any


_ANNOTATION_TYPES = {"text", "stroke"}


def serializable_desk_annotations(
    annotations: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Return a JSON-safe copy of desk annotations for layout persistence."""
    serialized: list[dict[str, Any]] = []
    for annotation in annotations:
        if not isinstance(annotation, dict):
            continue
        item_type = str(annotation.get("type") or "")
        if item_type not in _ANNOTATION_TYPES:
            continue
        clean = dict(annotation)
        if item_type == "stroke":
            clean["points"] = _serializable_points(clean.get("points"))
            if len(clean["points"]) < 2:
                continue
        serialized.append(clean)
    return serialized


def _serializable_points(points: Any) -> list[list[float]]:
    """Normalize stroke points to JSON-friendly ``[x, y]`` pairs."""
    normalized: list[list[float]] = []
    for point in list(points or []):
        try:
            x, y = point
            normalized.append([float(x), float(y)])
        except (TypeError, ValueError):
            continue
    return normalized
