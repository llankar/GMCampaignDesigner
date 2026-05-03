"""UI entrypoint for launching onboarding tours."""
from __future__ import annotations

from collections.abc import Callable, Mapping
from tkinter import messagebox

from app.onboarding import TourEngine, TourStateStore, build_tour_registry

DEFAULT_TOUR_ID = "new_gm_mvp"


class GuidedTourLauncher:
    def __init__(self) -> None:
        self._engine: TourEngine | None = None

    @staticmethod
    def _build_widget_resolver(widget_registry) -> Callable[[str, str], object | None]:
        """Build a widget resolver callable from either a function or a mapping."""
        if callable(widget_registry):
            return widget_registry
        if isinstance(widget_registry, Mapping):
            return lambda _screen, key: widget_registry.get(key)
        raise TypeError("widget_registry must be callable or mapping-like")

    def launch_guided_tour(self, root_window, widget_registry, current_screen_getter, *, tour_id: str = DEFAULT_TOUR_ID) -> bool:
        if self._engine is not None and getattr(self._engine, "_tour_id", None):
            return False
        tours = build_tour_registry()
        if tour_id not in tours:
            messagebox.showwarning("Guided Tour", f"Tour '{tour_id}' is unavailable.")
            return False
        widget_resolver = self._build_widget_resolver(widget_registry)
        self._engine = TourEngine(
            root_window,
            tours,
            widget_resolver,
            screen_resolver=current_screen_getter,
            state_store=TourStateStore(),
        )
        self._engine.start(tour_id)
        return True


_launcher = GuidedTourLauncher()


def launch_guided_tour(root_window, widget_registry, current_screen_getter):
    return _launcher.launch_guided_tour(root_window, widget_registry, current_screen_getter)
