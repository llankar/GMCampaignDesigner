"""Regression tests for image browser virtualization rerender behavior."""

from __future__ import annotations

from dataclasses import dataclass

from modules.ui.image_library.browser_panel import ImageBrowserPanel
from modules.ui.image_library.result_card import ImageResult


@dataclass
class _ToolbarStateStub:
    size_preset: str = "Medium"
    display_mode: str = "Grid"


class _WidgetStub:
    def __init__(self) -> None:
        self.last_config: dict[str, object] = {}
        self.grid_called = False
        self.grid_forget_called = False

    def configure(self, **kwargs) -> None:
        self.last_config.update(kwargs)

    def grid(self, **_kwargs) -> None:
        self.grid_called = True

    def grid_forget(self) -> None:
        self.grid_forget_called = True


class _ItemsFrameStub:
    def __init__(self) -> None:
        self.columns: list[int] = []

    def grid_columnconfigure(self, col: int, weight: int) -> None:
        self.columns.append((col, weight))


class _CardStub:
    def __init__(self, *_args, **_kwargs) -> None:
        self.destroy_called = False
        self.grid_calls: list[dict[str, object]] = []

    def grid(self, **kwargs) -> None:
        self.grid_calls.append(kwargs)

    def winfo_exists(self) -> bool:
        return True

    def destroy(self) -> None:
        self.destroy_called = True


class _ScrollableStub:
    _parent_canvas = None


class _ToolbarStub:
    state = _ToolbarStateStub()


def test_render_visible_subset_skips_clearing_when_window_is_unchanged(monkeypatch) -> None:
    """Two renders with same visible window should keep existing cards."""
    monkeypatch.setattr("modules.ui.image_library.browser_panel.ImageResultCard", _CardStub)

    panel = ImageBrowserPanel.__new__(ImageBrowserPanel)
    panel._virtualization_job = None
    panel._filtered_records = [ImageResult(path="/tmp/image.png", name="image")]
    panel._top_spacer = _WidgetStub()
    panel._bottom_spacer = _WidgetStub()
    panel._empty_label = _WidgetStub()
    panel._items_frame = _ItemsFrameStub()
    panel.scrollable = _ScrollableStub()
    panel.toolbar = _ToolbarStub()
    panel._row_overscan = 2
    panel._visible_window = None
    panel._last_render_signature = None
    panel._active_cards = []
    panel._ctk_images = []
    panel._open_callback = lambda _item: None
    panel._view_callback = lambda _item: None
    panel._show_context_menu = lambda _item, _x, _y: None
    panel._load_ctk_thumb = lambda _path, _size: object()

    panel._render_visible_subset()

    assert len(panel._active_cards) == 1
    first_card = panel._active_cards[0]

    panel._render_visible_subset()

    assert panel._active_cards == [first_card]
    assert not first_card.destroy_called
