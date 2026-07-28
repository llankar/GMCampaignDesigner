"""Lifecycle coordination for progress toplevels.

CustomTkinter schedules some platform-specific toplevel initialization after the
window is constructed.  An unusually fast worker can otherwise destroy the Tcl
window before those callbacks run (most visibly on Windows).
"""

from __future__ import annotations

import time
from typing import Callable, Optional


class ProgressDialogLifecycle:
    """Keep a progress toplevel valid until its initialization has settled."""

    def __init__(self, owner, window, *, minimum_lifetime_ms: int = 250) -> None:
        self.owner = owner
        self.window = window
        self.minimum_lifetime_ms = max(0, minimum_lifetime_ms)
        self.closing = False
        self.destroyed = False
        self._created_at = time.monotonic()
        self._after_ids: set[object] = set()
        self._close_after_id: Optional[object] = None
        self._completion_claimed = False

    def window_exists(self) -> bool:
        """Return whether Tcl still owns the window without leaking Tcl errors."""
        if self.destroyed:
            return False
        try:
            return bool(self.window.winfo_exists())
        except Exception:
            return False

    def can_update(self) -> bool:
        """Return whether an application callback may still touch the dialog."""
        return not self.closing and self.window_exists()

    def schedule_update(self, callback: Callable[[], None]) -> bool:
        """Schedule a guarded UI update, ignoring progress arriving after close."""
        # Progress callbacks normally arrive on a worker thread.  Do not call
        # any Tk method here; the guarded event-loop callback performs the Tcl
        # existence check on the UI thread.
        if self.closing or self.destroyed:
            return False

        token: dict[str, object] = {}

        def guarded() -> None:
            after_id = token.get("id")
            if after_id is not None:
                self._after_ids.discard(after_id)
            if self.can_update():
                callback()

        after_id = self.owner.after(0, guarded)
        token["id"] = after_id
        self._after_ids.add(after_id)
        return True

    def close(self, on_closed: Optional[Callable[[], None]] = None) -> bool:
        """Claim completion once and destroy safely after the minimum lifetime."""
        if self._completion_claimed:
            return False
        self._completion_claimed = True
        self.closing = True
        self._cancel_updates()

        elapsed_ms = int((time.monotonic() - self._created_at) * 1000)
        delay_ms = max(0, self.minimum_lifetime_ms - elapsed_ms)
        self._close_after_id = self.owner.after(
            delay_ms, lambda: self._destroy_and_notify(on_closed)
        )
        return True

    def _cancel_updates(self) -> None:
        for after_id in tuple(self._after_ids):
            try:
                self.owner.after_cancel(after_id)
            except Exception:
                pass
            finally:
                self._after_ids.discard(after_id)

    def _destroy_and_notify(self, on_closed: Optional[Callable[[], None]]) -> None:
        self._close_after_id = None
        self._cancel_updates()
        if self.window_exists():
            try:
                self.window.grab_release()
            except Exception:
                pass
            if self.window_exists():
                try:
                    self.window.destroy()
                except Exception:
                    pass
        self.destroyed = True
        if on_closed is not None:
            on_closed()
