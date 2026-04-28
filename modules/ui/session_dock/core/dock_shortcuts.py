"""Keyboard shortcut wiring for the session dock."""

from __future__ import annotations

from collections.abc import Callable

import customtkinter as ctk


class DockShortcutManager:
    """Manage bind/unbind lifecycle of dock shortcuts."""

    def __init__(self, root: ctk.CTkBaseClass) -> None:
        self._root = root
        self._bindings: list[tuple[str, str]] = []

    def bind(self, sequence: str, callback: Callable[[], None]) -> None:
        """Register a global sequence on the application root."""
        bind_id = self._root.bind_all(sequence, lambda _event: callback(), add="+")
        self._bindings.append((sequence, bind_id))

    def clear(self) -> None:
        """Remove all registered bindings."""
        for sequence, bind_id in self._bindings:
            self._root.unbind_all(sequence)
            if bind_id:
                # Tk does not support selective unbind_all by id; kept for future updates.
                _ = bind_id
        self._bindings.clear()
