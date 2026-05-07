"""Measurement template helpers for battle maps and world maps."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, Literal, Sequence

MEASUREMENT_ITEM_TYPE = "measurement"
MEASUREMENT_TEMPLATE_TYPES = ("line", "path", "cone", "circle", "square", "aura")
MEASUREMENT_TEMPLATE_LABELS = [name.capitalize() for name in MEASUREMENT_TEMPLATE_TYPES]
MEASUREMENT_LABEL_TO_TYPE = {label: value for label, value in zip(MEASUREMENT_TEMPLATE_LABELS, MEASUREMENT_TEMPLATE_TYPES)}
MEASUREMENT_TYPE_TO_LABEL = {value: label for label, value in MEASUREMENT_LABEL_TO_TYPE.items()}
DEFAULT_GRID_CELL_PIXELS = 50.0
DEFAULT_GRID_SCALE = 5.0
DEFAULT_DISTANCE_UNIT = "ft"

Point = tuple[float, float]


@dataclass(frozen=True)
class MeasurementStyle:
    """Canvas styling for rendered measurement templates."""

    outline: str = "#45B7FF"
    fill: str = "#45B7FF"
    label_fill: str = "#FFFFFF"
    label_bg: str = "#101828"
    width: int = 3
    dash: tuple[int, int] = (8, 4)
    stipple: str = "gray25"


def normalize_template_type(value: str | None) -> str:
    """Return a known template type, defaulting to line."""

    normalized = (value or "line").strip().lower()
    if normalized in MEASUREMENT_TEMPLATE_TYPES:
        return normalized
    return MEASUREMENT_LABEL_TO_TYPE.get((value or "").strip(), "line")


def label_for_template_type(template_type: str | None) -> str:
    """Return a human-friendly template type label."""

    return MEASUREMENT_TYPE_TO_LABEL.get(normalize_template_type(template_type), "Line")


def coerce_float(value, default: float) -> float:
    """Safely coerce a value to float."""

    try:
        converted = float(value)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(converted) or converted <= 0:
        return default
    return converted


def distance_between(start: Point, end: Point) -> float:
    """Return Euclidean distance between two points."""

    return math.hypot(end[0] - start[0], end[1] - start[1])


def measurement_distance(pixels: float, *, grid_cell_pixels: float, grid_scale: float) -> float:
    """Convert pixel distance into configured map units."""

    cell_pixels = coerce_float(grid_cell_pixels, DEFAULT_GRID_CELL_PIXELS)
    scale = coerce_float(grid_scale, DEFAULT_GRID_SCALE)
    return (max(0.0, float(pixels)) / cell_pixels) * scale


def format_distance(value: float, unit: str = DEFAULT_DISTANCE_UNIT) -> str:
    """Format a measurement distance compactly for a canvas label."""

    suffix = unit or DEFAULT_DISTANCE_UNIT
    if abs(value - round(value)) < 0.05:
        return f"{int(round(value))} {suffix}"
    return f"{value:.1f} {suffix}"


def _bbox_from_points(points: Sequence[Point]) -> tuple[float, float, float, float]:
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    return min(xs), min(ys), max(xs), max(ys)


def cone_polygon(start: Point, end: Point, angle_degrees: float = 53.13) -> list[Point]:
    """Build a cone wedge polygon from a start point toward an end point."""

    length = distance_between(start, end)
    if length <= 0:
        return [start, end, end]
    heading = math.atan2(end[1] - start[1], end[0] - start[0])
    half_angle = math.radians(angle_degrees / 2.0)
    left = (start[0] + math.cos(heading - half_angle) * length, start[1] + math.sin(heading - half_angle) * length)
    right = (start[0] + math.cos(heading + half_angle) * length, start[1] + math.sin(heading + half_angle) * length)
    return [start, left, right]


def build_measurement_item(
    template_type: str,
    start: Point,
    end: Point,
    *,
    grid_cell_pixels: float = DEFAULT_GRID_CELL_PIXELS,
    grid_scale: float = DEFAULT_GRID_SCALE,
    unit: str = DEFAULT_DISTANCE_UNIT,
) -> dict:
    """Create a persistent measurement-template map item."""

    template_type = normalize_template_type(template_type)
    start = (float(start[0]), float(start[1]))
    end = (float(end[0]), float(end[1]))
    return {
        "type": MEASUREMENT_ITEM_TYPE,
        "template_type": template_type,
        "position": start,
        "points": [start, end],
        "grid_cell_pixels": coerce_float(grid_cell_pixels, DEFAULT_GRID_CELL_PIXELS),
        "grid_scale": coerce_float(grid_scale, DEFAULT_GRID_SCALE),
        "unit": unit or DEFAULT_DISTANCE_UNIT,
        "canvas_ids": (),
    }


def serialize_measurement_item(item: dict) -> dict:
    """Return the storage payload for a measurement template item."""

    start, end = measurement_points(item)
    return {
        "type": MEASUREMENT_ITEM_TYPE,
        "template_type": normalize_template_type(item.get("template_type")),
        "x": start[0],
        "y": start[1],
        "points": [[start[0], start[1]], [end[0], end[1]]],
        "grid_cell_pixels": coerce_float(item.get("grid_cell_pixels"), DEFAULT_GRID_CELL_PIXELS),
        "grid_scale": coerce_float(item.get("grid_scale"), DEFAULT_GRID_SCALE),
        "unit": item.get("unit") or DEFAULT_DISTANCE_UNIT,
    }


def deserialize_measurement_item(payload: dict) -> dict:
    """Hydrate a stored measurement template item."""

    points = payload.get("points") or []
    if isinstance(points, Iterable):
        parsed = []
        for point in points:
            if isinstance(point, (list, tuple)) and len(point) >= 2:
                parsed.append((float(point[0]), float(point[1])))
    else:
        parsed = []
    if len(parsed) < 2:
        parsed = [(float(payload.get("x", 0)), float(payload.get("y", 0))), (float(payload.get("x", 0)), float(payload.get("y", 0)))]
    return build_measurement_item(
        payload.get("template_type"),
        parsed[0],
        parsed[-1],
        grid_cell_pixels=payload.get("grid_cell_pixels", DEFAULT_GRID_CELL_PIXELS),
        grid_scale=payload.get("grid_scale", DEFAULT_GRID_SCALE),
        unit=payload.get("unit", DEFAULT_DISTANCE_UNIT),
    )


def measurement_points(item: dict) -> tuple[Point, Point]:
    """Return start/end points from a measurement item."""

    points = item.get("points") or []
    parsed: list[Point] = []
    for point in points:
        if isinstance(point, (list, tuple)) and len(point) >= 2:
            parsed.append((float(point[0]), float(point[1])))
    if len(parsed) >= 2:
        return parsed[0], parsed[-1]
    position = item.get("position") or (item.get("x", 0), item.get("y", 0))
    start = (float(position[0]), float(position[1])) if isinstance(position, (list, tuple)) else (0.0, 0.0)
    return start, start


def measurement_label(item: dict) -> str:
    """Build a distance label for the measurement template."""

    start, end = measurement_points(item)
    template_type = normalize_template_type(item.get("template_type"))
    if template_type == "square":
        raw_distance = max(abs(end[0] - start[0]), abs(end[1] - start[1]))
    else:
        raw_distance = distance_between(start, end)
    distance = measurement_distance(
        raw_distance,
        grid_cell_pixels=item.get("grid_cell_pixels", DEFAULT_GRID_CELL_PIXELS),
        grid_scale=item.get("grid_scale", DEFAULT_GRID_SCALE),
    )
    formatted = format_distance(distance, item.get("unit") or DEFAULT_DISTANCE_UNIT)
    if template_type in {"circle", "aura"}:
        return f"R {formatted}"
    if template_type == "square":
        return f"Side {formatted}"
    if template_type == "cone":
        return f"Cone {formatted}"
    return formatted


def render_measurement_on_canvas(
    canvas,
    item: dict,
    world_to_screen,
    *,
    style: MeasurementStyle | None = None,
    tags: tuple[str, ...] = (),
) -> tuple[int, ...]:
    """Render a measurement template on a Tk canvas and return created ids."""

    style = style or MeasurementStyle()
    template_type = normalize_template_type(item.get("template_type"))
    start_world, end_world = measurement_points(item)
    sx, sy = world_to_screen(*start_world)
    ex, ey = world_to_screen(*end_world)
    common_tags = (MEASUREMENT_ITEM_TYPE, f"measurement_{template_type}", *tags)
    ids: list[int] = []

    if template_type in {"line", "path"}:
        ids.append(canvas.create_line(sx, sy, ex, ey, fill=style.outline, width=style.width, arrow="last", tags=common_tags))
        label_anchor = ((sx + ex) / 2.0, (sy + ey) / 2.0)
    elif template_type == "cone":
        screen_poly = []
        for wx, wy in cone_polygon(start_world, end_world):
            px, py = world_to_screen(wx, wy)
            screen_poly.extend([px, py])
        ids.append(
            canvas.create_polygon(
                *screen_poly,
                fill=style.fill,
                outline=style.outline,
                width=style.width,
                stipple=style.stipple,
                tags=common_tags,
            )
        )
        label_anchor = (ex, ey)
    else:
        radius = distance_between((sx, sy), (ex, ey))
        if template_type == "square":
            side = max(abs(ex - sx), abs(ey - sy))
            ex_square = sx + (side if ex >= sx else -side)
            ey_square = sy + (side if ey >= sy else -side)
            ids.append(
                canvas.create_rectangle(
                    sx,
                    sy,
                    ex_square,
                    ey_square,
                    fill=style.fill,
                    outline=style.outline,
                    width=style.width,
                    stipple=style.stipple,
                    tags=common_tags,
                )
            )
            label_anchor = ((sx + ex_square) / 2.0, (sy + ey_square) / 2.0)
        else:
            ids.append(
                canvas.create_oval(
                    sx - radius,
                    sy - radius,
                    sx + radius,
                    sy + radius,
                    fill=style.fill,
                    outline=style.outline,
                    width=style.width,
                    stipple=style.stipple,
                    tags=common_tags,
                )
            )
            label_anchor = (sx, sy - radius)

    label_text = measurement_label(item)
    lx, ly = label_anchor
    text_id = canvas.create_text(lx, ly - 10, text=label_text, fill=style.label_fill, font=("Segoe UI", 12, "bold"), tags=common_tags)
    bbox = canvas.bbox(text_id)
    if bbox:
        pad = 4
        bg_id = canvas.create_rectangle(
            bbox[0] - pad,
            bbox[1] - pad,
            bbox[2] + pad,
            bbox[3] + pad,
            fill=style.label_bg,
            outline=style.outline,
            tags=common_tags,
        )
        canvas.tag_lower(bg_id, text_id)
        ids.extend([bg_id, text_id])
    else:
        ids.append(text_id)
    return tuple(ids)
