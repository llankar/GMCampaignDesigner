from __future__ import annotations

import logging
import time
from typing import Any, Callable

from .tour_models import TourStep
from .tour_overlay import TourOverlay
from .tour_popover import TourPopover
from .tour_state import TourStateStore
from .widget_locator import WidgetLocator

logger = logging.getLogger(__name__)


class TourEngine:
    def __init__(
        self,
        root: Any,
        tours: dict[str, list[TourStep]],
        widget_resolver: Callable[[str, str], Any],
        screen_resolver: Callable[[], str],
        state_store: TourStateStore | None = None,
        user_notifier: Callable[[str], None] | None = None,
        on_stop: Callable[[], None] | None = None,
        resolution_timeout_seconds: float = 1.5,
    ) -> None:
        self._root = root
        self._tours = tours
        self._screen_resolver = screen_resolver
        self._state_store = state_store or TourStateStore()
        self._resolution_timeout_seconds = max(resolution_timeout_seconds, 0.0)
        self._screen_poll_interval_seconds = 0.05
        self._overlay = TourOverlay(root)
        self._popover = TourPopover(root, self.next_step, self.prev_step, self.stop)
        self._widget_locator = WidgetLocator(
            widget_resolver,
            root=root,
            timeout_seconds=resolution_timeout_seconds,
        )
        self._user_notifier = user_notifier or (lambda _: None)
        self._on_stop = on_stop
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
        was_active = self._tour_id is not None
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
        if was_active and self._on_stop:
            try:
                self._on_stop()
            except Exception:
                logger.exception("Guided tour stop callback failed.")

    @property
    def current_step(self) -> TourStep | None:
        if 0 <= self._step_index < len(self._steps):
            return self._steps[self._step_index]
        return None

    def _advance(self, direction: int) -> None:
        next_index = self._step_index + direction
        notified_unresolved_targets: set[tuple[str, str, str | None]] = set()
        if not 0 <= next_index < len(self._steps):
            self.stop()
            return

        step = self._steps[next_index]
        if self._try_show_step(step, notified_unresolved_targets=notified_unresolved_targets):
            self._step_index = next_index
            return

        if self._step_index < 0:
            self.stop()

    def _try_show_step(
        self,
        step: TourStep,
        *,
        notified_unresolved_targets: set[tuple[str, str, str | None]] | None = None,
    ) -> bool:
        if not self._wait_for_screen(step.screen):
            reason = f"screen '{step.screen}' is not active"
            self._log_skipped_step(step, reason)
            self._notify_unresolved_target_once(step, reason, notified_unresolved_targets)
            return False

        if step.before_hook:
            step.before_hook(step)

        resolved = self._widget_locator.resolve(step.screen, step.target_widget_key)
        target_widget = resolved.widget
        if target_widget is None:
            reason = f"widget '{step.target_widget_key}' not visible"
            self._log_skipped_step(step, reason)
            self._notify_unresolved_target_once(step, reason, notified_unresolved_targets, resolved.message)
            return False

        self._overlay.show_highlight(target_widget)
        self._popover.show(step, target_widget)
        return True

    def _wait_for_screen(self, expected_screen: str) -> bool:
        deadline = time.monotonic() + self._resolution_timeout_seconds
        while True:
            if self._screen_resolver() == expected_screen:
                return True
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return False
            self._pump_ui()
            time.sleep(min(self._screen_poll_interval_seconds, remaining))

    def _pump_ui(self) -> None:
        for method_name in ("update_idletasks", "update"):
            updater = getattr(self._root, method_name, None)
            if callable(updater):
                try:
                    updater()
                except Exception:
                    continue

    def _notify_unresolved_target_once(
        self,
        step: TourStep,
        reason: str,
        notified_unresolved_targets: set[tuple[str, str, str | None]] | None,
        resolver_message: str | None = None,
    ) -> None:
        unresolved_target = (step.screen, reason, resolver_message)
        if notified_unresolved_targets is not None:
            if unresolved_target in notified_unresolved_targets:
                return
            notified_unresolved_targets.add(unresolved_target)
        self._notify_unresolved_target(step, reason, resolver_message)

    def _notify_unresolved_target(self, step: TourStep, reason: str, resolver_message: str | None = None) -> None:
        message = resolver_message or f"Unable to show guided tour step '{step.id}': {reason}."
        self._user_notifier(message)

    def _log_skipped_step(self, step: TourStep, reason: str) -> None:
        logger.info("Skipping step '%s': %s.", step.id, reason)
