"""Reusable motion helpers for GM dashboard interactions."""

from __future__ import annotations

from typing import Callable


class MotionController:
    """Lightweight animation helper with accessibility support."""

    def __init__(self, scheduler: Callable[[int, Callable[[], None]], str], *, reduced_motion: bool = False):
        """Initialize motion controller."""
        self._schedule = scheduler
        self._reduced_motion = bool(reduced_motion)

    @property
    def reduced_motion(self) -> bool:
        """Return whether reduced motion is enabled."""
        return self._reduced_motion

    def set_reduced_motion(self, enabled: bool) -> None:
        """Enable/disable motion globally."""
        self._reduced_motion = bool(enabled)

    def pulse_widget(
        self,
        widget,
        *,
        duration_ms: int = 160,
        scale: float = 1.05,
        steps: int = 8,
    ) -> None:
        """Briefly pulse the widget to emphasize an important interaction."""
        if self._reduced_motion or widget is None:
            return
        base_width = _read_numeric(widget, "width")
        base_height = _read_numeric(widget, "height")
        if base_width is None and base_height is None:
            return

        half = max(1, steps // 2)
        frame_ms = max(12, duration_ms // max(1, steps))

        def _tick(index: int) -> None:
            if not _widget_alive(widget):
                return
            up = index < half
            segment = index if up else max(0, steps - index)
            ratio = segment / max(1, half)
            factor = 1 + ((scale - 1) * ratio)
            if base_width is not None:
                widget.configure(width=max(1, int(base_width * factor)))
            if base_height is not None:
                widget.configure(height=max(1, int(base_height * factor)))

            if index < steps:
                self._schedule(frame_ms, lambda i=index + 1: _tick(i))
                return

            if base_width is not None:
                widget.configure(width=base_width)
            if base_height is not None:
                widget.configure(height=base_height)

        _tick(0)

    def fade_in_window(self, window, *, duration_ms: int = 180, steps: int = 8) -> None:
        """Fade in a toplevel window using alpha transitions."""
        if window is None or not _widget_alive(window):
            return
        if self._reduced_motion:
            _safe_alpha(window, 1.0)
            return

        frame_ms = max(12, duration_ms // max(1, steps))
        _safe_alpha(window, 0.0)

        def _tick(index: int) -> None:
            if not _widget_alive(window):
                return
            alpha = min(1.0, index / max(1, steps))
            _safe_alpha(window, alpha)
            if index < steps:
                self._schedule(frame_ms, lambda i=index + 1: _tick(i))

        _tick(0)

    def slide_up_widget(self, widget, *, distance_px: int = 16, duration_ms: int = 180, steps: int = 8) -> None:
        """Slide a place-managed widget upward while restoring its final position."""
        if self._reduced_motion or widget is None or not _widget_alive(widget):
            return

        info = widget.place_info()
        if not info:
            return

        try:
            original_y = int(float(info.get("y", 0)))
        except Exception:
            return

        frame_ms = max(12, duration_ms // max(1, steps))
        start_y = original_y + max(0, distance_px)
        widget.place_configure(y=start_y)

        def _tick(index: int) -> None:
            if not _widget_alive(widget):
                return
            progress = min(1.0, index / max(1, steps))
            current_y = int(start_y - ((start_y - original_y) * progress))
            widget.place_configure(y=current_y)
            if index < steps:
                self._schedule(frame_ms, lambda i=index + 1: _tick(i))
                return
            widget.place_configure(y=original_y)

        _tick(0)


def _widget_alive(widget) -> bool:
    try:
        return bool(widget.winfo_exists())
    except Exception:
        return False


def _read_numeric(widget, option: str) -> int | None:
    try:
        value = widget.cget(option)
    except Exception:
        return None
    try:
        numeric = int(float(value))
    except Exception:
        return None
    return numeric if numeric > 0 else None


def _safe_alpha(window, alpha: float) -> None:
    try:
        window.wm_attributes("-alpha", max(0.0, min(1.0, alpha)))
    except Exception:
        return
