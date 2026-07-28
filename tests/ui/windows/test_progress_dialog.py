"""Regression tests for short-lived CustomTkinter progress dialogs."""

from __future__ import annotations

import heapq

from modules.ui.windows.progress_dialog import ProgressDialogLifecycle


class FakeOwner:
    def __init__(self) -> None:
        self.now = 0
        self._next_id = 0
        self._callbacks = []
        self.cancelled = set()

    def after(self, delay, callback):
        self._next_id += 1
        after_id = f"after-{self._next_id}"
        heapq.heappush(self._callbacks, (self.now + delay, self._next_id, after_id, callback))
        return after_id

    def after_cancel(self, after_id):
        self.cancelled.add(after_id)

    def run_next(self):
        while self._callbacks:
            due, _, after_id, callback = heapq.heappop(self._callbacks)
            if after_id in self.cancelled:
                continue
            self.now = due
            callback()
            return True
        return False

    def run_all(self):
        while self.run_next():
            pass


class FakeToplevel:
    def __init__(self, owner: FakeOwner, *, delayed_setup: bool = True) -> None:
        self.owner = owner
        self.exists = True
        self.calls = []
        self.invalid_calls = []
        if delayed_setup:
            self.owner.after(200, self.deiconify)
            self.owner.after(200, self.focus_force)

    def winfo_exists(self):
        return self.exists

    def _record(self, operation):
        if not self.exists:
            self.invalid_calls.append(operation)
        else:
            self.calls.append(operation)

    def configure(self, **_kwargs):
        self._record("configure")

    def deiconify(self):
        self._record("deiconify")

    def focus_force(self):
        self._record("focus")

    def grab_release(self):
        self._record("grab_release")

    def destroy(self):
        self._record("destroy")
        self.exists = False


def test_immediate_worker_completion_keeps_dialog_alive_for_delayed_setup():
    owner = FakeOwner()
    window = FakeToplevel(owner)
    lifecycle = ProgressDialogLifecycle(owner, window)
    completions = []
    progress_callback = lambda: lifecycle.schedule_update(
        lambda: window.configure(text="late")
    )

    # Model a worker which reports progress and returns before the event loop runs.
    progress_callback()
    assert lifecycle.close(lambda: completions.append("success"))
    assert not lifecycle.close(lambda: completions.append("duplicate"))

    # A worker reporting again after completion must not enqueue another UI update.
    assert progress_callback() is False
    owner.run_all()

    assert window.calls == ["deiconify", "focus", "grab_release", "destroy"]
    assert window.invalid_calls == []
    assert completions == ["success"]
    assert lifecycle.closing is True
    assert lifecycle.destroyed is True


def test_guarded_update_rechecks_tcl_window_before_touching_widgets():
    owner = FakeOwner()
    window = FakeToplevel(owner, delayed_setup=False)
    lifecycle = ProgressDialogLifecycle(owner, window, minimum_lifetime_ms=0)

    assert lifecycle.schedule_update(lambda: window.configure(text="progress"))
    window.exists = False  # Simulate destruction outside the lifecycle.
    owner.run_all()

    assert window.invalid_calls == []
