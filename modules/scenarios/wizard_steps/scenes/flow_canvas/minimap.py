from __future__ import annotations


def world_to_minimap(
    world_x: float,
    world_y: float,
    *,
    world_bounds: tuple[float, float, float, float],
    minimap_bounds: tuple[float, float, float, float],
) -> tuple[float, float]:
    min_world_x, min_world_y, max_world_x, max_world_y = world_bounds
    mini_left, mini_top, mini_right, mini_bottom = minimap_bounds
    world_w = max(1.0, float(max_world_x - min_world_x))
    world_h = max(1.0, float(max_world_y - min_world_y))
    mini_w = max(1.0, float(mini_right - mini_left))
    mini_h = max(1.0, float(mini_bottom - mini_top))
    px = (float(world_x) - min_world_x) / world_w
    py = (float(world_y) - min_world_y) / world_h
    return mini_left + px * mini_w, mini_top + py * mini_h


def minimap_to_world(
    minimap_x: float,
    minimap_y: float,
    *,
    world_bounds: tuple[float, float, float, float],
    minimap_bounds: tuple[float, float, float, float],
) -> tuple[float, float]:
    min_world_x, min_world_y, max_world_x, max_world_y = world_bounds
    mini_left, mini_top, mini_right, mini_bottom = minimap_bounds
    world_w = max(1.0, float(max_world_x - min_world_x))
    world_h = max(1.0, float(max_world_y - min_world_y))
    mini_w = max(1.0, float(mini_right - mini_left))
    mini_h = max(1.0, float(mini_bottom - mini_top))
    px = (float(minimap_x) - mini_left) / mini_w
    py = (float(minimap_y) - mini_top) / mini_h
    return min_world_x + px * world_w, min_world_y + py * world_h

