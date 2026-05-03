from __future__ import annotations

from typing import Any


class TourOverlay:
    """Visual overlay helper used to focus/highlight a target widget."""

    def __init__(self, root: Any) -> None:
        self._root = root
        self._current_target: Any = None
        self._configure_bind = self._root.bind("<Configure>", self._on_configure, add="+")

    def show_highlight(self, target_widget: Any) -> None:
        self._current_target = target_widget
        self.refresh_geometry()

    def clear(self) -> None:
        self._current_target = None

    def refresh_geometry(self) -> None:
        if self._current_target is None:
            return
        updater = getattr(self._current_target, "update_idletasks", None)
        if callable(updater):
            updater()

    def _on_configure(self, _event: Any) -> None:
        self.refresh_geometry()
