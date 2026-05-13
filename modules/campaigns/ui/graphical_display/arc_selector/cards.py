"""Canvas drawing primitives for campaign arc selector cards."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class CanvasLike(Protocol):
    """Small protocol for the tkinter Canvas methods used by these helpers."""

    def create_rectangle(self, *args, **kwargs): ...
    def create_polygon(self, *args, **kwargs): ...
    def create_text(self, *args, **kwargs): ...


_TITLE_Y_OFFSET = 45
_META_Y_OFFSET = 72
_PROGRESS_Y_OFFSET = 91
_TITLE_TO_META_MIN_GAP = 24


@dataclass(frozen=True, slots=True)
class ArcCardColors:
    """Resolved colors used to draw one selector card."""

    fill: str
    outline: str
    title: str
    eyebrow: str
    meta: str
    status_text: str
    status_fill: str
    progress_track: str
    progress_fill: str
    accent: str


@dataclass(frozen=True, slots=True)
class ArcCardMetrics:
    """Geometry for an arc selector card."""

    x1: float
    y1: float
    x2: float
    y2: float
    width: float
    height: float
    content_x: float
    content_right: float
    title_y: float
    meta_y: float
    progress_y: float


@dataclass(frozen=True, slots=True)
class ArcCardPayload:
    """Display payload for one arc selector card."""

    index: int
    name: str
    status: str
    scenario_count: int
    completed_scenarios: int = 0


def calculate_arc_card_metrics(x1: float, y1: float, card_width: float, card_height: float) -> ArcCardMetrics:
    """Return padded geometry for an arc selector card."""
    content_x = x1 + 16
    content_right = x1 + card_width - 16
    title_y = y1 + _TITLE_Y_OFFSET
    meta_y = max(y1 + _META_Y_OFFSET, title_y + _TITLE_TO_META_MIN_GAP)
    return ArcCardMetrics(
        x1=x1,
        y1=y1,
        x2=x1 + card_width,
        y2=y1 + card_height,
        width=card_width,
        height=card_height,
        content_x=content_x,
        content_right=content_right,
        title_y=title_y,
        meta_y=meta_y,
        progress_y=y1 + _PROGRESS_Y_OFFSET,
    )


def draw_arc_card(
    canvas: CanvasLike,
    metrics: ArcCardMetrics,
    payload: ArcCardPayload,
    colors: ArcCardColors,
    *,
    tags: tuple[str, ...],
) -> None:
    """Draw a clean campaign arc selector card on a canvas."""
    radius = 14
    _rounded_rectangle(
        canvas,
        metrics.x1,
        metrics.y1,
        metrics.x2,
        metrics.y2,
        radius,
        fill=colors.fill,
        outline=colors.outline,
        width=2,
        tags=tags,
    )
    canvas.create_rectangle(
        metrics.x1 + 1,
        metrics.y1 + 12,
        metrics.x1 + 4,
        metrics.y2 - 12,
        fill=colors.accent,
        outline="",
        tags=tags,
    )

    canvas.create_text(
        metrics.content_x,
        metrics.y1 + 18,
        text=f"ARC {payload.index + 1}",
        fill=colors.eyebrow,
        anchor="w",
        font=("Segoe UI", 9, "bold"),
        tags=tags,
    )
    _draw_status_pill(canvas, metrics, payload.status, colors, tags=tags)

    title_limit = _title_limit_for_width(metrics.width)
    canvas.create_text(
        metrics.content_x,
        metrics.title_y,
        text=truncate_to_width(payload.name, title_limit),
        fill=colors.title,
        anchor="nw",
        font=("Segoe UI", 12, "bold"),
        tags=tags,
    )

    canvas.create_text(
        metrics.content_x,
        metrics.meta_y,
        text=scenario_count_label(payload.scenario_count),
        fill=colors.meta,
        anchor="w",
        font=("Segoe UI", 9),
        tags=tags,
    )
    _draw_progress(canvas, metrics, payload, colors, tags=tags)


def scenario_count_label(count: int) -> str:
    """Return a compact scenario count label with correct pluralization."""
    safe_count = max(int(count or 0), 0)
    noun = "scenario" if safe_count == 1 else "scenarios"
    return f"{safe_count} {noun}"


def truncate_to_width(value: str, limit: int) -> str:
    """Truncate text for a fixed-width canvas card."""
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    ellipsis = "..."
    return text[: max(limit - len(ellipsis), 0)].rstrip() + ellipsis


def _title_limit_for_width(width: float) -> int:
    """Estimate a single-line title budget for a Segoe UI 12 bold canvas label."""
    chars_per_line = max(int((width - 32) / 6), 14)
    return min(chars_per_line, 34)


def _draw_status_pill(
    canvas: CanvasLike,
    metrics: ArcCardMetrics,
    status: str,
    colors: ArcCardColors,
    *,
    tags: tuple[str, ...],
) -> None:
    status_text = truncate_to_width(status or "Planned", 14)
    pill_width = min(max(len(status_text) * 7 + 18, 68), max(metrics.width * 0.45, 68))
    x2 = metrics.content_right
    x1 = x2 - pill_width
    y1 = metrics.y1 + 9
    y2 = y1 + 20
    _rounded_rectangle(
        canvas,
        x1,
        y1,
        x2,
        y2,
        10,
        fill=colors.status_fill,
        outline="",
        width=1,
        tags=tags,
    )
    canvas.create_text(
        (x1 + x2) / 2,
        (y1 + y2) / 2,
        text=status_text,
        fill=colors.status_text,
        anchor="center",
        font=("Segoe UI", 8, "bold"),
        tags=tags,
    )


def _draw_progress(
    canvas: CanvasLike,
    metrics: ArcCardMetrics,
    payload: ArcCardPayload,
    colors: ArcCardColors,
    *,
    tags: tuple[str, ...],
) -> None:
    track_x1 = metrics.content_x
    track_x2 = metrics.content_right
    track_y1 = metrics.progress_y
    track_y2 = metrics.progress_y + 4
    _rounded_rectangle(
        canvas,
        track_x1,
        track_y1,
        track_x2,
        track_y2,
        2,
        fill=colors.progress_track,
        outline="",
        width=1,
        tags=tags,
    )

    total = max(payload.scenario_count, 1)
    completed = max(min(payload.completed_scenarios, total), 0)
    if completed <= 0:
        return
    fill_x2 = track_x1 + ((track_x2 - track_x1) * (completed / total))
    _rounded_rectangle(
        canvas,
        track_x1,
        track_y1,
        fill_x2,
        track_y2,
        2,
        fill=colors.progress_fill,
        outline="",
        width=1,
        tags=tags,
    )


def _rounded_rectangle(
    canvas: CanvasLike,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    radius: float,
    **kwargs,
) -> None:
    """Draw a rounded rectangle using a smoothed polygon."""
    points = [
        x1 + radius,
        y1,
        x2 - radius,
        y1,
        x2,
        y1,
        x2,
        y1 + radius,
        x2,
        y2 - radius,
        x2,
        y2,
        x2 - radius,
        y2,
        x1 + radius,
        y2,
        x1,
        y2,
        x1,
        y2 - radius,
        x1,
        y1 + radius,
        x1,
        y1,
    ]
    if hasattr(canvas, "create_polygon"):
        canvas.create_polygon(points, smooth=True, splinesteps=8, **kwargs)
        return

    # Lightweight test canvases often only implement rectangles; keep those paths importable.
    canvas.create_rectangle(x1, y1, x2, y2, **kwargs)
