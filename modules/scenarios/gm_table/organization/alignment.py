"""Pure alignment and sizing helpers for GM Table organization actions."""

from __future__ import annotations

from .layout_tools import align_geometries, distribute_geometries, eligible_panel_records


def same_size_geometries(geometries: list[dict], dimension: str) -> list[dict]:
    """Return copies resized to the largest width, height, or both dimensions."""
    if dimension not in {"width", "height", "both"}:
        raise ValueError(f"Unsupported same-size dimension: {dimension}")
    copies = [dict(geometry) for geometry in geometries]
    if not copies:
        return []
    if dimension in {"width", "both"}:
        width = max(int(g["width"]) for g in copies)
        for geometry in copies:
            geometry["width"] = width
    if dimension in {"height", "both"}:
        height = max(int(g["height"]) for g in copies)
        for geometry in copies:
            geometry["height"] = height
    return copies


def snap_geometries_to_grid(geometries: list[dict], grid_size: int = 24) -> list[dict]:
    """Return copies with origins snapped to the nearest grid point."""
    grid = max(1, int(grid_size))
    copies = [dict(geometry) for geometry in geometries]
    for geometry in copies:
        geometry["x"] = round(float(geometry["x"]) / grid) * grid
        geometry["y"] = round(float(geometry["y"]) / grid) * grid
    return copies
