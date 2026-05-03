"""Shared registry for guided-tour target widgets across windows/dialogs."""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable


class TourWidgetRegistry:
    """Register and resolve widgets by stable (screen, key) identifiers."""

    def __init__(self) -> None:
        self._entries: dict[str, dict[str, object]] = defaultdict(dict)

    def register(self, screen: str, key: str, widget: object) -> None:
        """Register or replace a widget target."""
        if not screen or not key:
            return
        self._entries[screen][key] = widget

    def unregister(self, screen: str, key: str) -> None:
        """Unregister a widget target if present."""
        per_screen = self._entries.get(screen)
        if not per_screen:
            return
        per_screen.pop(key, None)
        if not per_screen:
            self._entries.pop(screen, None)

    def resolver(self) -> Callable[[str, str], object | None]:
        """Build a guided-tour resolver callable."""

        def _resolve(screen: str, key: str) -> object | None:
            widget = self._entries.get(screen, {}).get(key)
            if widget is None:
                return None
            exists = getattr(widget, "winfo_exists", None)
            if callable(exists) and not exists():
                self.unregister(screen, key)
                return None
            return widget

        return _resolve
