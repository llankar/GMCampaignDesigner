"""Explicit sizing strategies for GM table panel layouts."""

from __future__ import annotations

from typing import Any

PANEL_MARGIN = 12
PANEL_GUTTER = 12


DEFAULT_CONTENT_MINIMUMS: dict[str, tuple[int, int]] = {
    "campaign_dashboard": (780, 560),
    "world_map": (860, 620),
    "map_tool": (900, 640),
    "scene_flow": (860, 600),
    "image_library": (860, 580),
    "handouts": (760, 560),
    "loot_generator": (620, 520),
    "whiteboard": (900, 640),
    "random_tables": (680, 560),
    "plot_twists": (460, 320),
    "entity": (580, 520),
    "puzzle_display": (700, 540),
    "character_graph": (860, 620),
    "scenario_graph": (860, 620),
    "note": (520, 360),
}


def _clamp(value: int, minimum: int, maximum: int) -> int:
    return max(minimum, min(maximum, value))


def _surface_dimensions(surface: Any, *, minimum_width: int = 640, minimum_height: int = 420) -> tuple[int, int]:
    try:
        width = int(surface.winfo_width())
    except Exception:
        width = minimum_width
    try:
        height = int(surface.winfo_height())
    except Exception:
        height = minimum_height
    return max(minimum_width, width), max(minimum_height, height)


def _constrain_panel_geometry(
    x: int,
    y: int,
    width: int,
    height: int,
    *,
    surface_w: int,
    surface_h: int,
    min_width: int,
    min_height: int,
    margin: int = PANEL_MARGIN,
) -> dict[str, int]:
    max_width = max(min_width, int(surface_w) - (margin * 2))
    max_height = max(min_height, int(surface_h) - (margin * 2))
    width = _clamp(int(width), int(min_width), max_width)
    height = _clamp(int(height), int(min_height), max_height)
    x = _clamp(int(x), margin, max(margin, int(surface_w) - width - margin))
    y = _clamp(int(y), margin, max(margin, int(surface_h) - height - margin))
    return {"x": x, "y": y, "width": width, "height": height}


def fit_viewport_snap(panel, surface, mode: str) -> dict[str, int]:
    """Return viewport-relative geometry for snap/magnets regardless of world camera."""
    min_width = max(1, int(getattr(panel, "MIN_WIDTH", 300)))
    min_height = max(1, int(getattr(panel, "MIN_HEIGHT", 220)))
    surface_w, surface_h = _surface_dimensions(surface)

    full_width = max(min_width, int(surface_w) - (PANEL_MARGIN * 2))
    full_height = max(min_height, int(surface_h) - (PANEL_MARGIN * 2))
    split_width = max(min_width * 2, full_width - PANEL_GUTTER)
    split_height = max(min_height * 2, full_height - PANEL_GUTTER)
    half_width = max(min_width, split_width // 2)
    half_height = max(min_height, split_height // 2)
    strip_height = _clamp(
        int(round(full_height * 0.28)),
        min_height,
        max(min_height, full_height - min_height - PANEL_GUTTER),
    )

    if mode == "maximize":
        return _constrain_panel_geometry(
            PANEL_MARGIN,
            PANEL_MARGIN,
            full_width,
            full_height,
            surface_w=surface_w,
            surface_h=surface_h,
            min_width=min_width,
            min_height=min_height,
        )

    mode_map: dict[str, tuple[int, int, int, int]] = {
        "left": (PANEL_MARGIN, PANEL_MARGIN, half_width, full_height),
        "right": (surface_w - PANEL_MARGIN - half_width, PANEL_MARGIN, half_width, full_height),
        "top": (PANEL_MARGIN, PANEL_MARGIN, full_width, half_height),
        "bottom": (PANEL_MARGIN, surface_h - PANEL_MARGIN - half_height, full_width, half_height),
        "top_left": (PANEL_MARGIN, PANEL_MARGIN, half_width, half_height),
        "top_right": (surface_w - PANEL_MARGIN - half_width, PANEL_MARGIN, half_width, half_height),
        "bottom_left": (PANEL_MARGIN, surface_h - PANEL_MARGIN - half_height, half_width, half_height),
        "bottom_right": (surface_w - PANEL_MARGIN - half_width, surface_h - PANEL_MARGIN - half_height, half_width, half_height),
        "top_strip": (PANEL_MARGIN, PANEL_MARGIN, full_width, strip_height),
        "bottom_strip": (PANEL_MARGIN, surface_h - PANEL_MARGIN - strip_height, full_width, strip_height),
    }

    if mode not in mode_map:
        raise ValueError(f"Unsupported snap mode: {mode}")

    x, y, width, height = mode_map[mode]
    return _constrain_panel_geometry(
        x,
        y,
        width,
        height,
        surface_w=surface_w,
        surface_h=surface_h,
        min_width=min_width,
        min_height=min_height,
    )


def fit_content_minimum(panel_kind: str, state: dict | None) -> dict[str, int]:
    """Return readable minimum content dimensions for a panel kind and payload."""
    kind = str(panel_kind or "entity")
    width, height = DEFAULT_CONTENT_MINIMUMS.get(kind, DEFAULT_CONTENT_MINIMUMS["entity"])

    if kind == "entity":
        entity_type = str((state or {}).get("entity_type") or "").strip()
        if entity_type == "Scenarios":
            width, height = 920, 680
        elif entity_type in {"Informations", "Places", "Bases"}:
            width, height = 760, 580
        else:
            width, height = 680, 560

    return {"width": int(width), "height": int(height)}
