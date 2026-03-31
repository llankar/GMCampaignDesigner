"""Scheduling helpers for layout."""
from __future__ import annotations

from collections.abc import Callable
from typing import Any


class LayoutSettleScheduler:
    """Debounce layout work into a single idle-phase settle pass."""

    def __init__(self, host) -> None:
        """Initialize the LayoutSettleScheduler instance."""
        self.host = host
        self._jobs: dict[str, str] = {}
        try:
            self.host.bind("<Destroy>", self._on_destroy, add="+")
        except Exception:
            pass

    def _on_destroy(self, _event=None) -> None:
        """Handle destroy."""
        self.cancel_all()

    def cancel(self, key: str) -> None:
        """Handle cancel."""
        after_id = self._jobs.pop(key, None)
        if not after_id:
            return
        try:
            self.host.after_cancel(after_id)
        except Exception:
            pass

    def cancel_all(self) -> None:
        """Handle cancel all."""
        for key in list(self._jobs):
            self.cancel(key)

    def schedule(
        self,
        key: str,
        callback: Callable[[], Any],
        *,
        when: Callable[[], bool] | None = None,
        max_attempts: int = 8,
    ) -> None:
        """Schedule the operation."""
        self.cancel(key)

        def _run(attempts_left: int = max_attempts) -> None:
            """Run the operation."""
            self._jobs.pop(key, None)
            try:
                # Keep run resilient if this step fails.
                if hasattr(self.host, "winfo_exists") and not self.host.winfo_exists():
                    return
            except Exception:
                return

            ready = True
            if when is not None:
                try:
                    ready = bool(when())
                except Exception:
                    ready = False

            if ready:
                callback()
                return

            if attempts_left <= 0:
                return

            self._jobs[key] = self.host.after_idle(lambda: _run(attempts_left - 1))

        self._jobs[key] = self.host.after_idle(_run)

    def bind_configure(
        self,
        widget,
        key: str,
        callback: Callable[[], Any],
        *,
        when: Callable[[], bool] | None = None,
        max_attempts: int = 8,
        add: str = "+",
    ):
        """Bind configure."""
        def _handle(_event=None) -> None:
            """Internal helper for handle."""
            self.schedule(key, callback, when=when, max_attempts=max_attempts)

        widget.bind("<Configure>", _handle, add=add)
        return _handle
