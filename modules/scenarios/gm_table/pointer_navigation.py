"""Pointer gesture state for GM Table camera navigation."""

from __future__ import annotations

from dataclasses import dataclass


RIGHT_DRAG_THRESHOLD = 8


@dataclass(slots=True)
class RightDragGesture:
    """Track whether a right-button press has become a camera drag."""

    threshold: int = RIGHT_DRAG_THRESHOLD
    press_position: tuple[int, int] | None = None
    dragging: bool = False

    def begin(self, x: int, y: int) -> None:
        """Remember a right-button press without consuming its context click."""
        self.press_position = (int(x), int(y))
        self.dragging = False

    def update(self, x: int, y: int) -> bool:
        """Return whether movement has crossed the camera-drag threshold."""
        if self.press_position is None:
            return False
        press_x, press_y = self.press_position
        if not self.dragging:
            delta_x = int(x) - press_x
            delta_y = int(y) - press_y
            self.dragging = (delta_x * delta_x) + (delta_y * delta_y) >= self.threshold**2
        return self.dragging

    def finish(self) -> bool:
        """Reset the gesture and return whether it became a drag."""
        was_dragging = self.dragging
        self.press_position = None
        self.dragging = False
        return was_dragging
