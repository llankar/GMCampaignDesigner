from __future__ import annotations

import logging
from typing import Any, Callable, Iterable

from .tour_models import TourStep
from .tour_overlay import TourOverlay
from .tour_popover import TourPopover
from .tour_state import TourStateStore

logger = logging.getLogger(__name__)


class TourEngine:
    def __init__(
        self,
        root: Any,
        tours: dict[str, list[TourStep]],
        widget_resolver: Callable[[str, str], Any],
        screen_resolver: Callable[[], str],
        state_store: TourStateStore | None = None,
    ) -> None:
        self._root = root
        self._tours = tours
        self._widget_resolver = widget_resolver
        self._screen_resolver = screen_resolver
        self._state_store = state_store or TourStateStore()
        self._overlay = TourOverlay(root)
        self._popover = TourPopover(root, self.next_step, self.prev_step, self.stop)
        self._tour_id: str | None = None
        self._steps: list[TourStep] = []
        self._step_index = -1

    def start(self, tour_id: str) -> None:
        if tour_id not in self._tours:
            logger.warning("Tour '%s' does not exist.", tour_id)
            return
        self._tour_id = tour_id
        self._steps = self._tours[tour_id]
        self._step_index = -1
        self.next_step()

    def next_step(self) -> None:
        if not self._steps:
            return
        self._advance(1)

    def prev_step(self) -> None:
        if not self._steps:
            return
        self._advance(-1)

    def stop(self) -> None:
        current_step = self.current_step
        if current_step and current_step.after_hook:
            current_step.after_hook(current_step)

        self._overlay.clear()
        self._popover.hide()

        if self._tour_id and self._step_index >= len(self._steps) - 1:
            self._state_store.mark_tour_completed(self._tour_id)

        self._tour_id = None
        self._steps = []
        self._step_index = -1

    @property
    def current_step(self) -> TourStep | None:
        if 0 <= self._step_index < len(self._steps):
            return self._steps[self._step_index]
        return None

    def _advance(self, direction: int) -> None:
        next_index = self._step_index + direction
        while 0 <= next_index < len(self._steps):
            step = self._steps[next_index]
            if self._try_show_step(step):
                self._step_index = next_index
                return
            next_index += direction
        self.stop()

    def _try_show_step(self, step: TourStep) -> bool:
        if self._screen_resolver() != step.screen:
            logger.info(
                "Skipping step '%s': screen '%s' is not active.",
                step.id,
                step.screen,
            )
            return False

        target_widget = self._widget_resolver(step.screen, step.target_widget_key)
        if target_widget is None:
            logger.info(
                "Skipping step '%s': target widget '%s' was not found.",
                step.id,
                step.target_widget_key,
            )
            return False

        if step.before_hook:
            step.before_hook(step)

        self._overlay.show_highlight(target_widget)
        self._popover.show(step, target_widget)
        return True
