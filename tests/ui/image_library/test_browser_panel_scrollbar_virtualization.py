"""Regression tests for scrollbar-driven virtualization rerender behavior."""

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
        self.columns: list[tuple[int, int]] = []

    def grid_columnconfigure(self, col: int, weight: int) -> None:
        self.columns.append((col, weight))


class _CardStub:
    def __init__(self, *_args, **kwargs) -> None:
        self.item = kwargs["item"]
        self.destroy_called = False

    def grid(self, **_kwargs) -> None:
        return

    def winfo_exists(self) -> bool:
        return True

    def destroy(self) -> None:
        self.destroy_called = True


class _CanvasStub:
    def __init__(self) -> None:
        self._top_fraction = 0.0
        self.bindings: list[tuple[str, str]] = []

    def bind(self, event: str, _callback, add: str = "") -> None:
        self.bindings.append((event, add))

    def yview(self, *args):
        if len(args) == 2 and args[0] == "moveto":
            self._top_fraction = float(args[1])
        return (self._top_fraction, min(1.0, self._top_fraction + 0.25))

    def winfo_height(self) -> int:
        return 200


class _ScrollableStub:
    def __init__(self, canvas) -> None:
        self._parent_canvas = canvas


class _ToolbarStub:
    state = _ToolbarStateStub()


def test_scrollbar_yview_movement_rerenders_new_cards(monkeypatch) -> None:
    """Scrollbar-driven yview movement should trigger rendering of another virtual window."""
    monkeypatch.setattr("modules.ui.image_library.browser_panel.ImageResultCard", _CardStub)

    canvas = _CanvasStub()

    panel = ImageBrowserPanel.__new__(ImageBrowserPanel)
    panel._virtualization_job = None
    panel._filtered_records = [
        ImageResult(path=f"/tmp/image-{index}.png", name=f"image-{index}") for index in range(100)
    ]
    panel._top_spacer = _WidgetStub()
    panel._bottom_spacer = _WidgetStub()
    panel._empty_label = _WidgetStub()
    panel._items_frame = _ItemsFrameStub()
    panel.scrollable = _ScrollableStub(canvas)
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
    panel._schedule_virtualized_render = lambda force=False: panel._render_visible_subset()

    panel._bind_scroll_events()
    panel._render_visible_subset()

    first_item_at_top = panel._active_cards[0].item.path

    canvas.yview("moveto", "0.8")

    first_item_after_scrollbar_move = panel._active_cards[0].item.path

    assert first_item_after_scrollbar_move != first_item_at_top
    assert {
        ("<Configure>", "+"),
        ("<MouseWheel>", "+"),
        ("<Button-4>", "+"),
        ("<Button-5>", "+"),
    }.issubset(set(canvas.bindings))
