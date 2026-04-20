"""World-space alignment helpers for GM table floating panels."""

from __future__ import annotations

from dataclasses import dataclass
from math import sqrt


@dataclass(slots=True)
class AlignmentGuide:
    """Guide line descriptor in world coordinates."""

    axis: str
    world_value: float
    span_start: float
    span_end: float


def _edges(geometry: dict[str, float | int]) -> dict[str, float]:
    x = float(geometry.get("x", 0.0))
    y = float(geometry.get("y", 0.0))
    width = max(1.0, float(geometry.get("width", 1.0)))
    height = max(1.0, float(geometry.get("height", 1.0)))
    return {
        "left": x,
        "right": x + width,
        "top": y,
        "bottom": y + height,
        "center_x": x + (width / 2.0),
        "center_y": y + (height / 2.0),
    }


def nearest_edge_snap(
    active: dict[str, float | int],
    candidates: list[dict[str, float | int]],
    *,
    threshold: float = 24.0,
) -> dict[str, object]:
    """Return world-space edge snaps for active geometry against candidates."""
    active_edges = _edges(active)
    if not candidates:
        return {"x": float(active["x"]), "y": float(active["y"]), "guides": []}
    comparisons = (
        ("x", "left", "left"),
        ("x", "left", "right"),
        ("x", "right", "left"),
        ("x", "right", "right"),
        ("x", "center_x", "center_x"),
        ("y", "top", "top"),
        ("y", "top", "bottom"),
        ("y", "bottom", "top"),
        ("y", "bottom", "bottom"),
        ("y", "center_y", "center_y"),
    )
    best: dict[str, tuple[float, float, dict[str, float]]] = {}
    for candidate in candidates:
        candidate_edges = _edges(candidate)
        for axis, active_key, candidate_key in comparisons:
            delta = candidate_edges[candidate_key] - active_edges[active_key]
            distance = abs(delta)
            if distance > float(threshold):
                continue
            current = best.get(axis)
            if current is None or distance < current[0]:
                best[axis] = (distance, delta, candidate_edges)
    snapped_x = float(active.get("x", 0.0))
    snapped_y = float(active.get("y", 0.0))
    guides: list[AlignmentGuide] = []
    if "x" in best:
        _, delta_x, candidate = best["x"]
        snapped_x += delta_x
        guides.append(
            AlignmentGuide(
                axis="x",
                world_value=active_edges["left"] + delta_x,
                span_start=min(active_edges["top"], candidate["top"]),
                span_end=max(active_edges["bottom"], candidate["bottom"]),
            )
        )
    if "y" in best:
        _, delta_y, candidate = best["y"]
        snapped_y += delta_y
        guides.append(
            AlignmentGuide(
                axis="y",
                world_value=active_edges["top"] + delta_y,
                span_start=min(active_edges["left"], candidate["left"]),
                span_end=max(active_edges["right"], candidate["right"]),
            )
        )
    return {"x": round(snapped_x, 2), "y": round(snapped_y, 2), "guides": guides}


def equal_spacing(rectangles: dict[str, dict[str, float | int]]) -> dict[str, float]:
    """Return x positions for a horizontal equal-spacing distribution."""
    if len(rectangles) < 3:
        return {}
    ordered = sorted(
        rectangles.items(),
        key=lambda item: float(item[1].get("x", 0.0)),
    )
    total_width = sum(max(1.0, float(geometry.get("width", 1.0))) for _, geometry in ordered)
    left = float(ordered[0][1].get("x", 0.0))
    last = ordered[-1][1]
    right = float(last.get("x", 0.0)) + max(1.0, float(last.get("width", 1.0)))
    gap = (right - left - total_width) / float(len(ordered) - 1)
    cursor = left
    positions: dict[str, float] = {}
    for panel_id, geometry in ordered:
        positions[panel_id] = round(cursor, 2)
        cursor += max(1.0, float(geometry.get("width", 1.0))) + gap
    return positions


def pack_cluster(
    rectangles: dict[str, dict[str, float | int]],
    *,
    gutter: float = 24.0,
) -> dict[str, tuple[float, float]]:
    """Pack floating windows into a compact left-to-right world cluster."""
    if not rectangles:
        return {}
    ordered = sorted(
        rectangles.items(),
        key=lambda item: (
            float(item[1].get("y", 0.0)),
            float(item[1].get("x", 0.0)),
        ),
    )
    min_x = min(float(geometry.get("x", 0.0)) for _, geometry in ordered)
    min_y = min(float(geometry.get("y", 0.0)) for _, geometry in ordered)
    total_area = sum(
        max(1.0, float(geometry.get("width", 1.0))) * max(1.0, float(geometry.get("height", 1.0)))
        for _, geometry in ordered
    )
    row_target = max(320.0, sqrt(total_area) * 1.3)

    placements: dict[str, tuple[float, float]] = {}
    cursor_x = min_x
    cursor_y = min_y
    row_height = 0.0
    for panel_id, geometry in ordered:
        width = max(1.0, float(geometry.get("width", 1.0)))
        height = max(1.0, float(geometry.get("height", 1.0)))
        if cursor_x > min_x and (cursor_x - min_x + width) > row_target:
            cursor_x = min_x
            cursor_y += row_height + gutter
            row_height = 0.0
        placements[panel_id] = (round(cursor_x, 2), round(cursor_y, 2))
        row_height = max(row_height, height)
        cursor_x += width + gutter
    return placements
