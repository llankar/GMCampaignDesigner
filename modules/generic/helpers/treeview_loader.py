import tkinter as tk
from typing import Callable, Iterable, List, Optional, Any


class TreeviewLoader:
    """Utility to insert rows into a Treeview in responsive chunks."""

    def __init__(self, tree: tk.Misc):
        self.tree = tree
        self._rows: List[Any] = []
        self._insert_callback: Optional[Callable[[Any], None]] = None
        self._chunk_size: int = 40
        self._delay_ms: int = 1
        self._job: Optional[str] = None
        self._index: int = 0
        self._on_complete: Optional[Callable[[], None]] = None

    def reset_tree(self) -> None:
        """Cancel pending work and clear the tree quickly."""
        self.cancel()
        try:
            self.tree.state(("disabled",))
        except Exception:
            pass
        self.tree.delete(*self.tree.get_children(""))
        try:
            self.tree.state(("!disabled",))
        except Exception:
            pass

    def cancel(self) -> None:
        if self._job:
            try:
                self.tree.after_cancel(self._job)
            except Exception:
                pass
            self._job = None

    def start(
        self,
        rows: Iterable[Any],
        insert_callback: Callable[[Any], None],
        *,
        chunk_size: int = 500,
        delay_ms: int = 1,
        on_complete: Optional[Callable[[], None]] = None,
        reset: bool = True,
    ) -> None:
        """Schedule rows for insertion.

        Args:
            rows: Iterable of payloads consumed by insert_callback.
            insert_callback: Callable used to insert a single payload.
            chunk_size: Number of rows to insert per batch.
            delay_ms: Delay between batches to keep the UI responsive.
            on_complete: Optional callback executed after all rows are inserted.
            reset: When True, clear any existing queue before scheduling.
        """
        if reset:
            self._rows = list(rows)
            self._index = 0
        else:
            self._rows.extend(rows)
        self._insert_callback = insert_callback
        self._chunk_size = max(1, int(chunk_size))
        self._delay_ms = max(1, int(delay_ms))
        self._on_complete = on_complete
        if self._job:
            self.cancel()
        self._run_next_chunk()

    def append(self, rows: Iterable[Any]) -> None:
        """Append rows to the existing queue and start if idle."""
        self._rows.extend(rows)
        if not self._job:
            self._run_next_chunk()

    def is_running(self) -> bool:
        return bool(self._job)

    def _run_next_chunk(self) -> None:
        if not self._insert_callback:
            return
        end = min(self._index + self._chunk_size, len(self._rows))
        for payload in self._rows[self._index:end]:
            self._insert_callback(payload)
        self._index = end
        if self._index < len(self._rows):
            self._job = self.tree.after(self._delay_ms, self._run_next_chunk)
        else:
            self._job = None
            if self._on_complete:
                self._on_complete()
