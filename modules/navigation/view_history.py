"""View history helpers for main-surface navigation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


RestoreCallable = Callable[[], Any]


@dataclass(slots=True)
class ViewSnapshot:
    """Represents a restorable main-surface view state."""

    kind: str
    restore_callable: RestoreCallable | None = None
    factory: RestoreCallable | None = None
    state: dict[str, Any] = field(default_factory=dict)

    def restore(self) -> Any:
        """Restore this snapshot using a direct callable or lazy factory."""
        if self.restore_callable is not None:
            return self.restore_callable()
        if self.factory is not None:
            return self.factory()
        return None


class ViewHistoryManager:
    """Tracks current view plus back/forward stacks."""

    def __init__(self) -> None:
        self.current: ViewSnapshot | None = None
        self.back_stack: list[ViewSnapshot] = []
        self.forward_stack: list[ViewSnapshot] = []

    def set_current(self, snapshot: ViewSnapshot | None) -> None:
        """Set current snapshot without touching history stacks."""
        self.current = snapshot

    def push_current_and_set(self, snapshot: ViewSnapshot | None) -> None:
        """Push current snapshot to back stack then set new current snapshot."""
        if self.current is not None:
            self.back_stack.append(self.current)
        self.forward_stack.clear()
        self.current = snapshot

    def can_go_back(self) -> bool:
        """Return whether a backward navigation target exists."""
        return bool(self.back_stack)

    def can_go_forward(self) -> bool:
        """Return whether a forward navigation target exists."""
        return bool(self.forward_stack)

    def navigate_back(self) -> ViewSnapshot | None:
        """Move one step back and return the snapshot to restore."""
        if not self.back_stack:
            return None
        if self.current is not None:
            self.forward_stack.append(self.current)
        self.current = self.back_stack.pop()
        return self.current

    def navigate_forward(self) -> ViewSnapshot | None:
        """Move one step forward and return the snapshot to restore."""
        if not self.forward_stack:
            return None
        if self.current is not None:
            self.back_stack.append(self.current)
        self.current = self.forward_stack.pop()
        return self.current
