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
        self._target_widget: Any = None
        self._configure_bind = self._root.bind("<Configure>", self._on_configure, add="+")

    def show(self, step: TourStep, target_widget: Any) -> None:
        _ = step
        self._visible = True
        self._target_widget = target_widget
        self.refresh_geometry()

    def hide(self) -> None:
        self._visible = False
        self._target_widget = None

    def refresh_geometry(self) -> None:
        if not self._visible or self._target_widget is None:
            return
        updater = getattr(self._target_widget, "update_idletasks", None)
        if callable(updater):
            updater()

    def _on_configure(self, _event: Any) -> None:
        self.refresh_geometry()
