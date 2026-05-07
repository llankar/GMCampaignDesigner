"""Helpers for token facing angles and arrow geometry."""

from __future__ import annotations

import math
from typing import Any

DEFAULT_FACING_ANGLE = 0.0


def normalize_facing_angle(value: Any, default: float = DEFAULT_FACING_ANGLE) -> float:
    """Return *value* as a clockwise canvas angle in degrees, normalized to [0, 360)."""
    try:
        angle = float(value)
    except (TypeError, ValueError):
        angle = float(default)
    if not math.isfinite(angle):
        angle = float(default)
    return angle % 360.0


def token_center(position: tuple[float, float] | list[float], size: float) -> tuple[float, float]:
    """Return the world-space center for a top-left token position and token size."""
    x, y = position
    half = float(size) / 2.0
    return float(x) + half, float(y) + half


def facing_vector(angle: Any) -> tuple[float, float]:
    """Return a unit vector for a clockwise canvas angle where 0° points right."""
    radians = math.radians(normalize_facing_angle(angle))
    return math.cos(radians), math.sin(radians)


def facing_angle_from_points(center_x: float, center_y: float, point_x: float, point_y: float) -> float:
    """Return the clockwise canvas angle from a center point to a target point."""
    return normalize_facing_angle(math.degrees(math.atan2(point_y - center_y, point_x - center_x)))


def facing_arrow_points(
    position: tuple[float, float] | list[float],
    size: float,
    angle: Any,
    *,
    zoom: float = 1.0,
    pan_x: float = 0.0,
    pan_y: float = 0.0,
    offset_x: float = 0.0,
    offset_y: float = 0.0,
    extension: float = 0.32,
) -> tuple[float, float, float, float]:
    """Return screen-space start/end coordinates for a token facing arrow."""
    center_x, center_y = token_center(position, size)
    vec_x, vec_y = facing_vector(angle)
    radius = float(size) / 2.0
    start_world_x = center_x + vec_x * radius * 0.15
    start_world_y = center_y + vec_y * radius * 0.15
    end_world_x = center_x + vec_x * radius * (1.0 + extension)
    end_world_y = center_y + vec_y * radius * (1.0 + extension)
    return (
        start_world_x * zoom + pan_x - offset_x,
        start_world_y * zoom + pan_y - offset_y,
        end_world_x * zoom + pan_x - offset_x,
        end_world_y * zoom + pan_y - offset_y,
    )


def facing_arrowhead_points(
    tip_x: float,
    tip_y: float,
    angle: Any,
    *,
    length: float,
    width: float | None = None,
) -> tuple[float, float, float, float, float, float]:
    """Return triangle polygon points for an arrowhead whose tip follows *angle*."""
    head_length = max(1.0, float(length))
    head_width = max(1.0, float(width if width is not None else head_length * 0.72))
    vec_x, vec_y = facing_vector(angle)
    base_x = float(tip_x) - vec_x * head_length
    base_y = float(tip_y) - vec_y * head_length
    perp_x = -vec_y
    perp_y = vec_x
    half_width = head_width / 2.0
    return (
        float(tip_x),
        float(tip_y),
        base_x + perp_x * half_width,
        base_y + perp_y * half_width,
        base_x - perp_x * half_width,
        base_y - perp_y * half_width,
    )
