"""Bounded undo/redo stack for image editor commands."""

from __future__ import annotations

from collections import deque

from modules.ui.image_library.editor.history.commands import HistoryCommand


class HistoryStack:
    """Stores reversible commands with bounded depth."""

    def __init__(self, *, max_depth: int = 50) -> None:
        self._undo: deque[HistoryCommand] = deque(maxlen=max(1, int(max_depth)))
        self._redo: list[HistoryCommand] = []

    @property
    def can_undo(self) -> bool:
        return bool(self._undo)

    @property
    def can_redo(self) -> bool:
        return bool(self._redo)

    def execute_command(self, command: HistoryCommand) -> None:
        command.execute()
        self._undo.append(command)
        self._redo.clear()

    def undo(self) -> bool:
        if not self._undo:
            return False
        command = self._undo.pop()
        command.undo()
        self._redo.append(command)
        return True

    def redo(self) -> bool:
        if not self._redo:
            return False
        command = self._redo.pop()
        command.execute()
        self._undo.append(command)
        return True

    def clear(self) -> None:
        self._undo.clear()
        self._redo.clear()
