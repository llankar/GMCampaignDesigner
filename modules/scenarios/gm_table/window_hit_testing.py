"""Screen-space hit testing for GM Table hosted windows."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import tkinter as tk


@dataclass(frozen=True, slots=True)
class ScreenBounds:
    """A widget's bounds in screen coordinates."""

    x: int
    y: int
    width: int
    height: int

    @property
    def right(self) -> int:
        """Return the exclusive right edge."""
        return self.x + self.width

    @property
    def bottom(self) -> int:
        """Return the exclusive bottom edge."""
        return self.y + self.height

    def contains(self, screen_x: int, screen_y: int) -> bool:
        """Return whether the point is inside these screen bounds."""
        return self.x <= screen_x < self.right and self.y <= screen_y < self.bottom


def pointer_screen_position(event) -> tuple[int, int]:
    """Return the current pointer position in screen coordinates."""
    widget = getattr(event, "widget", None)
    if isinstance(widget, tk.Widget):
        try:
            pointer_x, pointer_y = widget.winfo_pointerxy()
            return int(pointer_x), int(pointer_y)
        except Exception:
            pass
    return int(getattr(event, "x_root", 0) or 0), int(getattr(event, "y_root", 0) or 0)


def widget_screen_bounds(widget) -> ScreenBounds | None:
    """Return mapped widget bounds in screen coordinates, or None if unavailable."""
    if not isinstance(widget, tk.Widget):
        return None
    try:
        if not widget.winfo_exists() or not widget.winfo_ismapped():
            return None
        widget.update_idletasks()
        width = int(widget.winfo_width())
        height = int(widget.winfo_height())
        if width <= 1 or height <= 1:
            return None
        return ScreenBounds(
            x=int(widget.winfo_rootx()),
            y=int(widget.winfo_rooty()),
            width=width,
            height=height,
        )
    except Exception:
        return None


def point_in_any_bounds(screen_x: int, screen_y: int, bounds: Iterable[ScreenBounds]) -> bool:
    """Return whether a screen point is contained by any supplied bounds."""
    return any(bound.contains(screen_x, screen_y) for bound in bounds)


def map_tool_screen_bounds(
    panel_records: Iterable[dict[str, object]],
    *,
    map_tool_window=None,
) -> list[ScreenBounds]:
    """Return screen bounds for open MapTool windows hosted by the app."""
    bounds: list[ScreenBounds] = []
    if map_tool_window is not None:
        external_bound = widget_screen_bounds(map_tool_window)
        if external_bound is not None:
            bounds.append(external_bound)
    for record in panel_records:
        if record.get("layout_mode") == "minimized":
            continue
        definition = record.get("definition")
        kind = getattr(definition, "kind", "")
        if kind != "map_tool":
            continue
        bound = widget_screen_bounds(record.get("panel"))
        if bound is not None:
            bounds.append(bound)
    return bounds


def point_inside_map_tool(
    screen_x: int,
    screen_y: int,
    panel_records: Iterable[dict[str, object]],
    *,
    map_tool_window=None,
) -> bool:
    """Return whether a pointer is inside an open MapTool panel.

    If MapTool is closed, minimized, unmapped, or unavailable, this returns False so
    callers can fall back to their normal GM Table behavior.
    """
    return point_in_any_bounds(
        screen_x,
        screen_y,
        map_tool_screen_bounds(panel_records, map_tool_window=map_tool_window),
    )
