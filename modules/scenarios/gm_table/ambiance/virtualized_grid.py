"""Viewport-based virtualized list rendering for ambiance library cards."""

from __future__ import annotations

import math

import customtkinter as ctk


class VirtualizedWallpaperGrid:
    """Render only visible rows in a scrollable container and recycle widgets."""

    def __init__(
        self,
        scrollable: ctk.CTkScrollableFrame,
        *,
        row_height: int,
        overscan_rows: int,
        create_row,
        bind_row,
    ) -> None:
        self._scrollable = scrollable
        self._row_height = max(60, int(row_height))
        self._overscan_rows = max(1, int(overscan_rows))
        self._create_row = create_row
        self._bind_row = bind_row

        self._items: list = []
        self._pool: list[ctk.CTkFrame] = []
        self._virtual_job: str | None = None
        self._bound_canvas = None

        self._top_spacer = ctk.CTkFrame(scrollable, height=1, fg_color="transparent")
        self._top_spacer.grid(row=0, column=0, sticky="ew")
        self._top_spacer.grid_propagate(False)

        self._rows_frame = ctk.CTkFrame(scrollable, fg_color="transparent")
        self._rows_frame.grid(row=1, column=0, sticky="nsew")
        self._rows_frame.grid_columnconfigure(0, weight=1)

        self._bottom_spacer = ctk.CTkFrame(scrollable, height=1, fg_color="transparent")
        self._bottom_spacer.grid(row=2, column=0, sticky="ew")
        self._bottom_spacer.grid_propagate(False)

        self._bind_scroll_events()

    def set_items(self, items: list) -> None:
        self._items = list(items)
        self.refresh(force=True)

    def refresh(self, *, force: bool = False) -> None:
        if self._virtual_job:
            try:
                self._scrollable.after_cancel(self._virtual_job)
            except Exception:
                pass
            self._virtual_job = None
        delay = 0 if force else 20
        self._virtual_job = self._scrollable.after(delay, self._render_visible)

    def _bind_scroll_events(self) -> None:
        canvas = getattr(self._scrollable, "_parent_canvas", None)
        if canvas is None:
            self._scrollable.after(50, self._bind_scroll_events)
            return
        if self._bound_canvas is canvas:
            return
        self._bound_canvas = canvas
        canvas.bind("<Configure>", lambda _event: self.refresh(), add="+")
        canvas.bind("<MouseWheel>", lambda _event: self.refresh(), add="+")
        canvas.bind("<Button-4>", lambda _event: self.refresh(), add="+")
        canvas.bind("<Button-5>", lambda _event: self.refresh(), add="+")
        scrollbar = getattr(self._scrollable, "_scrollbar", None)
        if scrollbar is not None:
            scrollbar.bind("<B1-Motion>", lambda _event: self.refresh(), add="+")
            scrollbar.bind("<ButtonRelease-1>", lambda _event: self.refresh(force=True), add="+")

    def _render_visible(self) -> None:
        self._virtual_job = None
        total_rows = len(self._items)
        if total_rows <= 0:
            self._top_spacer.configure(height=1)
            self._bottom_spacer.configure(height=1)
            for card in self._pool:
                card.grid_remove()
            return

        canvas = getattr(self._scrollable, "_parent_canvas", None)
        viewport_height = 860
        scroll_top = 0.0
        if canvas is not None:
            viewport_height = max(80, int(canvas.winfo_height()))
            y0, _y1 = canvas.yview()
            total_height = total_rows * self._row_height
            scroll_top = max(0.0, float(y0) * float(total_height))

        first_visible = int(scroll_top // self._row_height)
        visible_rows = max(1, int(math.ceil(viewport_height / self._row_height)))
        start = max(0, first_visible - self._overscan_rows)
        end = min(total_rows, first_visible + visible_rows + self._overscan_rows)

        self._top_spacer.configure(height=max(1, start * self._row_height))
        self._bottom_spacer.configure(height=max(1, (total_rows - end) * self._row_height))

        needed = max(0, end - start)
        while len(self._pool) < needed:
            row = self._create_row(self._rows_frame)
            self._pool.append(row)

        for slot, card in enumerate(self._pool):
            if slot >= needed:
                card.grid_remove()
                continue
            item_index = start + slot
            card.grid(row=slot, column=0, sticky="ew", padx=4, pady=4)
            self._bind_row(card, self._items[item_index], item_index)
