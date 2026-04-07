from __future__ import annotations

from modules.ui.image_library.editor.history.history_stack import HistoryStack


class _CounterCommand:
    def __init__(self, state: dict[str, int], delta: int) -> None:
        self._state = state
        self._delta = delta

    def execute(self) -> None:
        self._state["value"] += self._delta

    def undo(self) -> None:
        self._state["value"] -= self._delta


def test_history_stack_undo_redo_cycle() -> None:
    state = {"value": 0}
    history = HistoryStack(max_depth=5)

    history.execute_command(_CounterCommand(state, 2))
    history.execute_command(_CounterCommand(state, 3))

    assert state["value"] == 5
    assert history.can_undo is True
    assert history.can_redo is False

    assert history.undo() is True
    assert state["value"] == 2
    assert history.can_redo is True

    assert history.redo() is True
    assert state["value"] == 5


def test_history_stack_respects_bounded_depth() -> None:
    state = {"value": 0}
    history = HistoryStack(max_depth=2)

    history.execute_command(_CounterCommand(state, 1))
    history.execute_command(_CounterCommand(state, 1))
    history.execute_command(_CounterCommand(state, 1))

    assert state["value"] == 3

    assert history.undo() is True
    assert state["value"] == 2
    assert history.undo() is True
    assert state["value"] == 1
    assert history.undo() is False
    assert state["value"] == 1


def test_execute_after_undo_clears_redo_stack() -> None:
    state = {"value": 0}
    history = HistoryStack(max_depth=4)

    history.execute_command(_CounterCommand(state, 1))
    history.execute_command(_CounterCommand(state, 1))
    assert history.undo() is True
    assert history.can_redo is True

    history.execute_command(_CounterCommand(state, 5))
    assert state["value"] == 6
    assert history.can_redo is False
