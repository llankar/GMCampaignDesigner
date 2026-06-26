"""Pure layout helpers for GM Table organization actions."""

from __future__ import annotations


def eligible_panel_records(records: list[dict]) -> list[dict]:
    """Return records that can be moved by bulk layout tools."""
    return [
        record for record in records
        if not record.get("locked") and record.get("layout_mode") != "minimized"
    ]


def align_geometries(geometries: list[dict], edge: str) -> list[dict]:
    """Return copies aligned to a shared edge or center axis."""
    if not geometries:
        return []
    copies = [dict(geometry) for geometry in geometries]
    if edge == "left":
        target = min(float(g["x"]) for g in copies)
        for g in copies: g["x"] = target
    elif edge == "right":
        target = max(float(g["x"]) + int(g["width"]) for g in copies)
        for g in copies: g["x"] = target - int(g["width"])
    elif edge == "top":
        target = min(float(g["y"]) for g in copies)
        for g in copies: g["y"] = target
    elif edge == "bottom":
        target = max(float(g["y"]) + int(g["height"]) for g in copies)
        for g in copies: g["y"] = target - int(g["height"])
    elif edge == "center_x":
        target = sum(float(g["x"]) + int(g["width"]) / 2 for g in copies) / len(copies)
        for g in copies: g["x"] = target - int(g["width"]) / 2
    elif edge == "center_y":
        target = sum(float(g["y"]) + int(g["height"]) / 2 for g in copies) / len(copies)
        for g in copies: g["y"] = target - int(g["height"]) / 2
    else:
        raise ValueError(f"Unsupported alignment: {edge}")
    return copies


def distribute_geometries(geometries: list[dict], axis: str) -> list[dict]:
    """Return copies distributed evenly by left/top origin.

    The returned list preserves the input order so callers can safely zip the
    result back to their original panel records after sorting internally by the
    distribution axis.
    """
    key = "x" if axis == "horizontal" else "y" if axis == "vertical" else None
    if key is None:
        raise ValueError(f"Unsupported distribution axis: {axis}")

    copies = [dict(geometry) for geometry in geometries]
    if len(copies) < 3:
        return copies

    ordered_indices = sorted(range(len(copies)), key=lambda index: float(copies[index][key]))
    start = float(copies[ordered_indices[0]][key])
    end = float(copies[ordered_indices[-1]][key])
    step = (end - start) / (len(ordered_indices) - 1)
    for position, original_index in enumerate(ordered_indices):
        copies[original_index][key] = start + (step * position)
    return copies
