"""High-performance image browsing panel with toolbar and virtualized rendering."""

from __future__ import annotations

import math
import os
import tkinter as tk
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

import customtkinter as ctk

from modules.ui.image_library.result_card import ImageResult, ImageResultCard
from modules.ui.image_library.thumbnail_cache import ThumbnailCache, ThumbnailPlaceholderFactory
from modules.ui.image_library.toolbar import ImageLibraryToolbar, SORT_OPTIONS, ToolbarState
from modules.ui.image_library.editor.image_editor_dialog import ImageEditorDialog
from modules.ui.image_viewer import show_portrait


SIZE_CONFIG = {
    "Small": {"thumb": (96, 96), "grid_columns": 6, "item_height": 150},
    "Medium": {"thumb": (136, 136), "grid_columns": 5, "item_height": 190},
    "Large": {"thumb": (176, 176), "grid_columns": 4, "item_height": 230},
    "Very Large": {"thumb": (220, 220), "grid_columns": 3, "item_height": 280},
}

LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class VirtualWindow:
    """Window boundaries for virtualized rendering."""

    start_row: int
    end_row: int


class ImageBrowserPanel(ctk.CTkFrame):
    """Image browser with debounce search, sorting, virtualization and cached thumbnails."""

    def __init__(
        self,
        parent,
        *,
        records: Iterable[ImageResult] | None = None,
        on_open: Callable[[ImageResult], None] | None = None,
        on_view: Callable[[ImageResult], None] | None = None,
        thumbnail_cache: ThumbnailCache | None = None,
        toolbar_state: ToolbarState | None = None,
        on_attach_to_entity: Callable[[ImageResult], None] | None = None,
        on_toolbar_state_changed: Callable[[ToolbarState], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self._records: list[ImageResult] = list(records or [])
        self._filtered_records: list[ImageResult] = []
        self._active_cards: list[ImageResultCard] = []
        self._ctk_images: list[ctk.CTkImage] = []

        self._open_callback = on_open or self._default_open
        self._view_callback = on_view or self._default_view
        self._thumbnail_cache = thumbnail_cache or ThumbnailCache(max_items=512)
        self._attach_callback = on_attach_to_entity
        self._toolbar_state_changed_callback = on_toolbar_state_changed

        self.toolbar = ImageLibraryToolbar(
            self,
            on_change=self._on_toolbar_changed,
            initial_state=toolbar_state,
        )
        self.toolbar.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 4))

        self.scrollable = ctk.CTkScrollableFrame(self)
        self.scrollable.grid(row=1, column=0, sticky="nsew", padx=8, pady=(4, 8))
        self.scrollable.grid_columnconfigure(0, weight=1)

        self._top_spacer = ctk.CTkFrame(self.scrollable, height=1, fg_color="transparent")
        self._top_spacer.grid(row=0, column=0, sticky="ew")
        self._top_spacer.grid_propagate(False)

        self._items_frame = ctk.CTkFrame(self.scrollable, fg_color="transparent")
        self._items_frame.grid(row=1, column=0, sticky="nsew")
        self._items_frame.grid_columnconfigure(0, weight=1)

        self._bottom_spacer = ctk.CTkFrame(self.scrollable, height=1, fg_color="transparent")
        self._bottom_spacer.grid(row=2, column=0, sticky="ew")
        self._bottom_spacer.grid_propagate(False)

        self._empty_label = ctk.CTkLabel(self._items_frame, text="No matching images")

        self._context_menu = tk.Menu(self, tearoff=0)
        self._context_item: ImageResult | None = None
        self._context_menu.add_command(label="Open", command=self._context_open)
        self._context_menu.add_command(label="View", command=self._context_view)
        self._context_menu.add_command(label="Edit", command=self._context_edit)
        self._context_menu.add_separator()
        self._context_menu.add_command(label="Attach to entity", command=self._context_attach)

        self._visible_window: VirtualWindow | None = None
        self._last_render_signature: tuple[str, int, int, int] | None = None
        self._virtualization_job: str | None = None
        self._row_overscan = 2
        self._scroll_bind_job: str | None = None
        self._scroll_events_bound = False
        self._bound_canvas = None
        self._bound_scrollbar = None
        self._scrollbar_poll_job: str | None = None
        self._scrollbar_interacting = False
        self._last_canvas_yview: tuple[float, float] | None = None

        self._ensure_scroll_bindings()
        self.bind("<Map>", self._on_widget_map, add="+")
        self.after_idle(self._ensure_scroll_bindings)
        self._apply_filters_and_render()

    def set_records(self, records: Iterable[ImageResult]) -> None:
        """Replace records and refresh the browser."""
        self._records = list(records)
        self._apply_filters_and_render(reset_scroll=True)

    def _on_widget_map(self, _event=None) -> None:
        """Retry canvas event binding when widget is mapped."""
        if not self._scroll_events_bound:
            self._ensure_scroll_bindings()

    def _ensure_scroll_bindings(self, retries: int = 20, delay_ms: int = 50) -> None:
        """Attach viewport-change bindings once scrollable canvas exists."""
        if self._scroll_events_bound:
            return

        if self._scroll_bind_job:
            try:
                self.after_cancel(self._scroll_bind_job)
            except Exception:
                pass
            self._scroll_bind_job = None

        canvas = getattr(self.scrollable, "_parent_canvas", None)
        if not canvas:
            if retries > 0:
                self._scroll_bind_job = self.after(
                    delay_ms,
                    lambda: self._ensure_scroll_bindings(retries=retries - 1, delay_ms=delay_ms),
                )
            else:
                LOGGER.warning(
                    "ImageBrowserPanel: unable to bind scroll events; scrollable canvas not found after retries."
                )
            return

        if self._bound_canvas is canvas:
            self._scroll_events_bound = True
            self._bind_scrollbar_events()
            return

        self._wrap_canvas_yview(canvas)
        canvas.bind("<Configure>", lambda _event: self._schedule_virtualized_render(), add="+")
        canvas.bind("<MouseWheel>", lambda _event: self._schedule_virtualized_render(), add="+")
        canvas.bind("<Button-4>", lambda _event: self._schedule_virtualized_render(), add="+")
        canvas.bind("<Button-5>", lambda _event: self._schedule_virtualized_render(), add="+")
        self._last_canvas_yview = canvas.yview()
        self._bound_canvas = canvas
        self._scroll_events_bound = True
        self._bind_scrollbar_events()

    def _bind_scrollbar_events(self) -> None:
        """Bind internal scrollbar drag events to keep virtualization in sync."""
        scrollbar = getattr(self.scrollable, "_scrollbar", None)
        if not scrollbar:
            return
        if self._bound_scrollbar is scrollbar and getattr(scrollbar, "_image_browser_scrollbar_bound", False):
            return

        if getattr(scrollbar, "_image_browser_scrollbar_bound", False):
            self._bound_scrollbar = scrollbar
            return

        scrollbar.bind("<ButtonPress-1>", self._on_scrollbar_button_press, add="+")
        scrollbar.bind("<B1-Motion>", self._on_scrollbar_drag_motion, add="+")
        scrollbar.bind("<ButtonRelease-1>", self._on_scrollbar_button_release, add="+")
        setattr(scrollbar, "_image_browser_scrollbar_bound", True)
        self._bound_scrollbar = scrollbar

    def _on_scrollbar_button_press(self, _event=None) -> None:
        """Warm up rerender pipeline and start yview polling while dragging."""
        self._scrollbar_interacting = True
        self._schedule_virtualized_render()
        self._start_scrollbar_position_poll()

    def _on_scrollbar_drag_motion(self, _event=None) -> None:
        """Force rerender attempts while the scrollbar thumb is dragged."""
        self._scrollbar_interacting = True
        self._schedule_virtualized_render()
        self._start_scrollbar_position_poll()

    def _on_scrollbar_button_release(self, _event=None) -> None:
        """Stop polling and force a final rerender at drag end."""
        self._scrollbar_interacting = False
        if self._scrollbar_poll_job:
            try:
                self.after_cancel(self._scrollbar_poll_job)
            except Exception:
                pass
            self._scrollbar_poll_job = None
        self._schedule_virtualized_render(force=True)

    def _start_scrollbar_position_poll(self) -> None:
        """Poll canvas yview during scrollbar interaction as a fallback hook."""
        if self._scrollbar_poll_job:
            return
        self._scrollbar_poll_job = self.after(16, self._poll_scrollbar_position_change)

    def _poll_scrollbar_position_change(self) -> None:
        """Trigger rerender when yview changes while scrollbar is being dragged."""
        self._scrollbar_poll_job = None
        canvas = getattr(self.scrollable, "_parent_canvas", None)
        if not canvas:
            return

        current_yview = canvas.yview()
        if self._last_canvas_yview != current_yview:
            self._last_canvas_yview = current_yview
            self._schedule_virtualized_render()

        if self._scrollbar_interacting:
            self._scrollbar_poll_job = self.after(16, self._poll_scrollbar_position_change)

    def _wrap_canvas_yview(self, canvas) -> None:
        """Wrap canvas yview to rerender after vertical scrollbar movement."""
        if getattr(canvas, "_image_browser_yview_wrapped", False):
            return

        original_yview = getattr(canvas, "yview", None)
        if not callable(original_yview):
            return

        def _wrapped_yview(*args):
            result = original_yview(*args)
            self._last_canvas_yview = original_yview()
            if args:
                self._schedule_virtualized_render()
            return result

        setattr(canvas, "yview", _wrapped_yview)
        setattr(canvas, "_image_browser_yview_wrapped", True)

    def _on_toolbar_changed(self, _state: ToolbarState) -> None:
        """Handle toolbar state updates."""
        if self._toolbar_state_changed_callback:
            self._toolbar_state_changed_callback(self.toolbar.state)
        self._apply_filters_and_render(reset_scroll=True)

    def _apply_filters_and_render(self, *, reset_scroll: bool = False) -> None:
        """Filter, sort and render current result set."""
        state = self.toolbar.state
        query = state.query.lower().strip()

        folder_name = (state.folder_name or "All").strip().lower()
        if folder_name and folder_name != "all":
            folder_filtered = [
                item
                for item in self._records
                if (item.source_folder_name or "").strip().lower() == folder_name
            ]
        else:
            folder_filtered = list(self._records)

        if query:
            self._filtered_records = [
                item for item in folder_filtered if query in item.name.lower() or query in item.path.lower()
            ]
        else:
            self._filtered_records = folder_filtered

        reverse = False
        if state.sort_by == "Name (A-Z)":
            key_fn = lambda item: item.name.lower()
        elif state.sort_by == "Name (Z-A)":
            key_fn = lambda item: item.name.lower()
            reverse = True
        elif state.sort_by == "Newest First":
            key_fn = lambda item: item.modified_ts
            reverse = True
        elif state.sort_by == "Oldest First":
            key_fn = lambda item: item.modified_ts
        elif state.sort_by == "Path (A-Z)":
            key_fn = lambda item: item.path.lower()
        else:
            key_fn = lambda item: item.name.lower()
            if state.sort_by not in SORT_OPTIONS:
                reverse = False

        self._filtered_records.sort(key=key_fn, reverse=reverse)

        if reset_scroll:
            canvas = getattr(self.scrollable, "_parent_canvas", None)
            if canvas:
                canvas.yview_moveto(0.0)

        self._visible_window = None
        self._last_render_signature = None
        self._schedule_virtualized_render(force=True)

    def _schedule_virtualized_render(self, force: bool = False) -> None:
        """Coalesce rapid UI events into one render pass."""
        if self._virtualization_job:
            self.after_cancel(self._virtualization_job)
        delay_ms = 0 if force else 16
        self._virtualization_job = self.after(delay_ms, self._render_visible_subset)

    def _render_visible_subset(self) -> None:
        """Render only rows currently visible in viewport (with overscan)."""
        self._virtualization_job = None

        if not self._filtered_records:
            self._clear_rendered_cards()
            self._visible_window = None
            self._last_render_signature = None
            self._top_spacer.configure(height=1)
            self._bottom_spacer.configure(height=1)
            self._empty_label.grid(row=0, column=0, padx=10, pady=16, sticky="w")
            return
        self._empty_label.grid_forget()

        state = self.toolbar.state
        size_info = SIZE_CONFIG.get(state.size_preset, SIZE_CONFIG["Medium"])
        display_mode = state.display_mode

        columns = size_info["grid_columns"] if display_mode == "Grid" else 1
        item_height = size_info["item_height"] if display_mode == "Grid" else max(90, size_info["thumb"][1] + 32)

        total_items = len(self._filtered_records)
        total_rows = max(1, math.ceil(total_items / columns))

        canvas = getattr(self.scrollable, "_parent_canvas", None)
        if not canvas:
            window = VirtualWindow(0, total_rows)
        else:
            y_top_fraction, _y_bottom_fraction = canvas.yview()
            canvas_height = max(1, canvas.winfo_height())
            approx_total_px = total_rows * item_height
            first_visible_px = y_top_fraction * approx_total_px
            first_visible_row = int(first_visible_px // item_height)
            visible_row_count = max(1, math.ceil(canvas_height / item_height))
            start_row = max(0, first_visible_row - self._row_overscan)
            end_row = min(total_rows, first_visible_row + visible_row_count + self._row_overscan)
            window = VirtualWindow(start_row, end_row)

        render_signature = (display_mode, columns, item_height, total_items)
        should_rerender = not (
            self._visible_window == window and self._last_render_signature == render_signature
        )
        if not should_rerender:
            return

        self._clear_rendered_cards()
        self._visible_window = window
        self._last_render_signature = render_signature

        self._top_spacer.configure(height=max(1, window.start_row * item_height))
        self._bottom_spacer.configure(height=max(1, (total_rows - window.end_row) * item_height))

        start_index = window.start_row * columns
        end_index = min(total_items, window.end_row * columns)

        for col in range(columns):
            self._items_frame.grid_columnconfigure(col, weight=1)

        thumb_size = size_info["thumb"]

        for offset, index in enumerate(range(start_index, end_index)):
            item = self._filtered_records[index]
            row = offset // columns
            col = offset % columns
            card = ImageResultCard(
                self._items_frame,
                item=item,
                image=self._load_ctk_thumb(item.path, thumb_size),
                display_mode=display_mode,
                on_open=self._open_callback,
                on_view=self._view_callback,
                on_context_menu=self._show_context_menu,
                on_attach=self._attach_callback,
            )
            padx = 8 if display_mode == "Grid" else 4
            pady = 8 if display_mode == "Grid" else 4
            card.grid(row=row, column=col, padx=padx, pady=pady, sticky="ew")
            self._active_cards.append(card)

    def _load_ctk_thumb(self, path: str, size: tuple[int, int]) -> ctk.CTkImage:
        """Fetch thumbnail from cache and wrap as CTk image."""
        try:
            image = self._thumbnail_cache.get_thumbnail(path, size)
        except Exception:
            image = ThumbnailPlaceholderFactory.build(size)

        ctk_img = ctk.CTkImage(light_image=image, dark_image=image, size=size)
        self._ctk_images.append(ctk_img)
        return ctk_img

    def _clear_rendered_cards(self) -> None:
        """Remove currently rendered widgets and image references."""
        for card in self._active_cards:
            if card.winfo_exists():
                card.destroy()
        self._active_cards.clear()
        self._ctk_images.clear()

    def _show_context_menu(self, item: ImageResult, x_root: int, y_root: int) -> None:
        """Open right-click context menu for one item."""
        self._context_item = item
        self._context_menu.entryconfigure("Attach to entity", state=("normal" if self._attach_callback else "disabled"))
        try:
            self._context_menu.tk_popup(x_root, y_root)
        finally:
            self._context_menu.grab_release()

    def _context_open(self) -> None:
        """Handle context menu open action."""
        if self._context_item:
            self._open_callback(self._context_item)

    def _context_view(self) -> None:
        """Handle context menu view action."""
        if self._context_item:
            self._view_callback(self._context_item)

    def _context_edit(self) -> None:
        """Open inline image editor for current context item."""
        if not self._context_item:
            return

        def _refresh_after_save(_saved_path: str) -> None:
            self._apply_filters_and_render()

        ImageEditorDialog(self, self._context_item.path, on_saved=_refresh_after_save)

    def _context_attach(self) -> None:
        """Handle optional attach action for callers embedding this browser."""
        if self._context_item and self._attach_callback:
            self._attach_callback(self._context_item)

    @staticmethod
    def _default_open(item: ImageResult) -> None:
        """Default open behavior when no callback is supplied."""
        ImageBrowserPanel._default_view(item)

    @staticmethod
    def _default_view(item: ImageResult) -> None:
        """Default view behavior matching app image preview flow."""
        if not item.path:
            return
        resolved = item.path
        if not os.path.isabs(resolved):
            resolved = str(Path(resolved).expanduser())
        show_portrait(resolved, title=item.name)


__all__ = ["ImageBrowserPanel", "ImageResult", "ThumbnailCache", "ToolbarState"]
