"""Drag coordination for the virtual GM Table workspace."""

from __future__ import annotations

from collections.abc import Callable

from modules.scenarios.gm_table.window_hit_testing import pointer_screen_position


class GMTableDragController:
    """Context-aware gatekeeper for GM Table drag gestures."""

    def __init__(self, *, should_block_middle_drag: Callable[[int, int], bool]) -> None:
        self._should_block_middle_drag = should_block_middle_drag

    def allows_middle_drag_start(self, event) -> bool:
        """Return whether a middle-button drag should start for the GM Table."""
        screen_x, screen_y = pointer_screen_position(event)
        return not self._should_block_middle_drag(screen_x, screen_y)
