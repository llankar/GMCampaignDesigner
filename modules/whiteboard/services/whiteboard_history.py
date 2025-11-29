import copy
from collections import deque
from typing import Deque, List, Dict, Any, Tuple


class WhiteboardHistory:
    """Track undo/redo history for whiteboard interactions."""

    def __init__(self, *, max_entries: int = 50):
        self._undo: Deque[List[Dict[str, Any]]] = deque(maxlen=max_entries)
        self._redo: Deque[List[Dict[str, Any]]] = deque(maxlen=max_entries)

    def reset(self, items: List[Dict[str, Any]]):
        self._undo.clear()
        self._redo.clear()
        self._undo.append(self._clone(items))

    def checkpoint(self, items: List[Dict[str, Any]]):
        self._undo.append(self._clone(items))
        self._redo.clear()

    def undo(self, current_items: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], bool]:
        if len(self._undo) <= 1:
            return current_items, False
        self._redo.append(self._clone(current_items))
        # The latest snapshot is the current state; discard it and return previous
        self._undo.pop()
        return self._clone(self._undo[-1]), True

    def redo(self, current_items: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], bool]:
        if not self._redo:
            return current_items, False
        self._undo.append(self._clone(current_items))
        next_state = self._redo.pop()
        return self._clone(next_state), True

    def _clone(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        sanitized: List[Dict[str, Any]] = []
        for item in items:
            cleaned = {k: v for k, v in item.items() if k not in ("canvas_ids", "_image_ref")}
            sanitized.append(copy.deepcopy(cleaned))
        return sanitized

