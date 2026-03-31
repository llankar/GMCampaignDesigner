"""Helpers for wiring right-click context menus on detail views."""

from __future__ import annotations

from collections import deque
from typing import Callable


ContextMenuHandler = Callable[..., object]


def bind_context_menu_recursively(root_widget, handler: ContextMenuHandler) -> None:
    """Bind right-click shortcuts on ``root_widget`` and all descendants.

    Tkinter does not always propagate right-click events from child widgets to
    parent frames. Detail views are deeply nested, so we explicitly bind each
    child to ensure the GM Screen context menu is available everywhere in a tab.
    """

    if root_widget is None or not callable(handler):
        return

    queue = deque([root_widget])
    while queue:
        # Keep looping while queue.
        widget = queue.popleft()
        try:
            widget.bind("<Button-3>", handler, add="+")
            widget.bind("<Control-Button-1>", handler, add="+")
        except Exception:
            # Some embedded widgets may reject binds; skip them safely.
            pass

        try:
            children = widget.winfo_children()
        except Exception:
            children = []

        for child in children:
            queue.append(child)
