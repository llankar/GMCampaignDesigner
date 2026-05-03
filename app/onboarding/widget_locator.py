from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class WidgetResolution:
    widget: Any | None
    message: str | None = None


class WidgetLocator:
    """Resolve widgets from stable keys and ensure they are renderable."""

    def __init__(
        self,
        widget_resolver: Callable[[str, str], Any],
        *,
        root: Any | None = None,
        timeout_seconds: float = 1.5,
        poll_interval_seconds: float = 0.05,
    ) -> None:
        self._widget_resolver = widget_resolver
        self._root = root
        self._timeout_seconds = max(timeout_seconds, 0.0)
        self._poll_interval_seconds = max(poll_interval_seconds, 0.01)

    def resolve(self, screen: str, key: str) -> WidgetResolution:
        deadline = time.monotonic() + self._timeout_seconds
        while True:
            widget = self._widget_resolver(screen, key)
            if self._is_visible(widget):
                return WidgetResolution(widget=widget)

            if time.monotonic() >= deadline:
                return WidgetResolution(
                    widget=None,
                    message=(
                        f"Impossible d'afficher l'étape: la cible '{key}' "
                        "n'est pas disponible pour le moment."
                    ),
                )

            self._pump_ui()
            time.sleep(self._poll_interval_seconds)

    def _pump_ui(self) -> None:
        if self._root is None:
            return
        updater = getattr(self._root, "update_idletasks", None)
        if callable(updater):
            updater()

    @staticmethod
    def _is_visible(widget: Any) -> bool:
        if widget is None:
            return False

        exists = getattr(widget, "winfo_exists", None)
        if callable(exists) and not exists():
            return False

        manager = getattr(widget, "winfo_manager", None)
        if callable(manager) and not manager():
            return False

        is_mapped = getattr(widget, "winfo_ismapped", None)
        if callable(is_mapped) and not is_mapped():
            return False

        viewable = getattr(widget, "winfo_viewable", None)
        if callable(viewable) and not viewable():
            return False

        return True
