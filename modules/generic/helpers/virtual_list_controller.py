import tkinter as tk
from typing import Callable, Optional


class VirtualListController:
    """Manage a virtualized scroll window for a row-based widget."""

    def __init__(
        self,
        tree: tk.Misc,
        scrollbar: tk.Scrollbar,
        *,
        row_height: int = 25,
        buffer_rows: int = 6,
    ) -> None:
        self.tree = tree
        self.scrollbar = scrollbar
        self.row_height = max(1, int(row_height))
        self.buffer_rows = max(0, int(buffer_rows))
        self.total_rows = 0
        self.window_rows = 1
        self.start_index = 0
        self._on_window_change: Optional[Callable[[int, int], None]] = None
        self._binding_ids = []

    def attach(self, on_window_change: Callable[[int, int], None]) -> None:
        self._on_window_change = on_window_change
        self.scrollbar.configure(command=self._on_scrollbar)
        self.tree.configure(yscrollcommand=self._on_tree_yview)
        self._bind_events()
        self._update_scrollbar()

    def detach(self) -> None:
        self._on_window_change = None
        for sequence, funcid in self._binding_ids:
            try:
                self.tree.unbind(sequence, funcid)
            except Exception:
                pass
        self._binding_ids.clear()

    def set_total_rows(self, total_rows: int) -> None:
        self.total_rows = max(0, int(total_rows))
        self._clamp_start()
        self._update_scrollbar()
        self._notify()

    def set_window_rows(self, window_rows: int) -> None:
        self.window_rows = max(1, int(window_rows))
        self._clamp_start()
        self._update_scrollbar()
        self._notify()

    def get_window(self) -> tuple[int, int]:
        return self.start_index, self.window_rows

    def refresh_window_for_height(self, height: int) -> None:
        visible = max(1, int(height / self.row_height))
        self.set_window_rows(visible + self.buffer_rows)

    def _bind_events(self) -> None:
        self._bind("<Configure>", self._on_configure)
        self._bind("<MouseWheel>", self._on_mousewheel)
        self._bind("<Button-4>", self._on_mousewheel)
        self._bind("<Button-5>", self._on_mousewheel)

    def _bind(self, sequence: str, func: Callable) -> None:
        funcid = self.tree.bind(sequence, func, add="+")
        if funcid:
            self._binding_ids.append((sequence, funcid))

    def _on_configure(self, event: tk.Event) -> None:
        try:
            height = int(getattr(event, "height", 0))
        except Exception:
            height = 0
        if height:
            self.refresh_window_for_height(height)

    def _on_tree_yview(self, _first: str, _last: str) -> None:
        # Ignore Treeview's internal scroll; the controller owns the scroll state.
        return

    def _on_scrollbar(self, *args: str) -> None:
        if not args:
            return
        if args[0] == "moveto" and len(args) > 1:
            try:
                fraction = float(args[1])
            except Exception:
                fraction = 0.0
            self._scroll_to_fraction(fraction)
            return
        if args[0] == "scroll" and len(args) > 2:
            try:
                amount = int(args[1])
            except Exception:
                amount = 0
            units = args[2]
            if units == "pages":
                delta = amount * max(1, self.window_rows - 1)
            else:
                delta = amount
            self._scroll_by_units(delta)

    def _on_mousewheel(self, event: tk.Event) -> str:
        delta = 0
        if getattr(event, "delta", 0):
            delta = int(-event.delta / 120)
        elif getattr(event, "num", None) == 4:
            delta = -1
        elif getattr(event, "num", None) == 5:
            delta = 1
        if delta:
            self._scroll_by_units(delta)
        return "break"

    def _scroll_to_fraction(self, fraction: float) -> None:
        max_start = max(0, self.total_rows - self.window_rows)
        target = int(round(fraction * max_start)) if max_start else 0
        self._set_start_index(target)

    def _scroll_by_units(self, delta: int) -> None:
        self._set_start_index(self.start_index + delta)

    def _set_start_index(self, start_index: int) -> None:
        self.start_index = int(start_index)
        self._clamp_start()
        self._update_scrollbar()
        self._notify()

    def _clamp_start(self) -> None:
        max_start = max(0, self.total_rows - self.window_rows)
        if self.start_index < 0:
            self.start_index = 0
        elif self.start_index > max_start:
            self.start_index = max_start

    def _update_scrollbar(self) -> None:
        if self.total_rows <= 0:
            self.scrollbar.set(0.0, 1.0)
            return
        start = self.start_index / self.total_rows
        end = min(1.0, (self.start_index + self.window_rows) / self.total_rows)
        self.scrollbar.set(start, end)

    def _notify(self) -> None:
        if self._on_window_change:
            self._on_window_change(self.start_index, self.window_rows)
