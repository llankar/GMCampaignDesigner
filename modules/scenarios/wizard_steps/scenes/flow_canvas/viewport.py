from __future__ import annotations

from typing import Iterable

ZOOM_MIN = 0.25
ZOOM_MAX = 2.5
NODE_WIDTH = 190.0
NODE_HEIGHT = 88.0
FIT_PADDING = 80.0


def clamp_zoom(value: float, *, minimum: float = ZOOM_MIN, maximum: float = ZOOM_MAX) -> float:
    return max(minimum, min(maximum, float(value)))


def compute_fit_viewport(nodes: Iterable[dict], canvas_width: float, canvas_height: float) -> dict[str, float]:
    width = max(1.0, float(canvas_width))
    height = max(1.0, float(canvas_height))
    node_list = list(nodes or [])
    if not node_list:
        return {"zoom": 1.0, "offset_x": 0.0, "offset_y": 0.0}

    left = min(float(n.get("x", 0.0)) for n in node_list) - FIT_PADDING
    top = min(float(n.get("y", 0.0)) for n in node_list) - FIT_PADDING
    right = max(float(n.get("x", 0.0)) + NODE_WIDTH for n in node_list) + FIT_PADDING
    bottom = max(float(n.get("y", 0.0)) + NODE_HEIGHT for n in node_list) + FIT_PADDING

    world_w = max(1.0, right - left)
    world_h = max(1.0, bottom - top)
    zoom = clamp_zoom(min(width / world_w, height / world_h))
    world_cx = (left + right) / 2.0
    world_cy = (top + bottom) / 2.0
    return {
        "zoom": zoom,
        "offset_x": (width / 2.0) - (world_cx * zoom),
        "offset_y": (height / 2.0) - (world_cy * zoom),
    }
