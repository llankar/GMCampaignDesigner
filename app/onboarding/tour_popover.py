from __future__ import annotations

from typing import Any, Callable

from .tour_models import TourStep


class TourPopover:
    """Text card + navigation controls for a tour step."""

    def __init__(
        self,
        root: Any,
        on_next: Callable[[], None],
        on_prev: Callable[[], None],
        on_close: Callable[[], None],
    ) -> None:
        self._root = root
        self._on_next = on_next
        self._on_prev = on_prev
        self._on_close = on_close
        self._visible = False

    def show(self, step: TourStep, target_widget: Any) -> None:
        _ = (step, target_widget)
        self._visible = True

    def hide(self) -> None:
        self._visible = False
