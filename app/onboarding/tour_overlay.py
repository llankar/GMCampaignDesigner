from __future__ import annotations

from typing import Any


class TourOverlay:
    """Visual overlay helper used to focus/highlight a target widget."""

    def __init__(self, root: Any) -> None:
        self._root = root
        self._current_target: Any = None

    def show_highlight(self, target_widget: Any) -> None:
        self._current_target = target_widget

    def clear(self) -> None:
        self._current_target = None
