"""Regression tests for image browser folder filtering from toolbar."""

from __future__ import annotations

from modules.ui.image_library.browser_panel import ImageBrowserPanel
from modules.ui.image_library.result_card import ImageResult


class _ToolbarStateStub:
    def __init__(self, folder_name: str) -> None:
        self.query = ""
        self.sort_by = "Name (A-Z)"
        self.folder_name = folder_name


class _ToolbarStub:
    def __init__(self, folder_name: str) -> None:
        self.state = _ToolbarStateStub(folder_name=folder_name)


def test_browser_panel_applies_folder_filter_from_toolbar() -> None:
    """Selecting a folder in the toolbar should narrow visible records."""
    panel = ImageBrowserPanel.__new__(ImageBrowserPanel)
    panel.toolbar = _ToolbarStub(folder_name="forests")
    panel._records = [
        ImageResult(path="/img/forests/one.png", name="One", source_folder_name="forests"),
        ImageResult(path="/img/dungeons/two.png", name="Two", source_folder_name="dungeons"),
    ]
    panel._schedule_virtualized_render = lambda force=False: None
    panel.scrollable = type("_ScrollableStub", (), {"_parent_canvas": None})()
    panel._filtered_records = []
    panel._visible_window = None
    panel._last_render_signature = None

    panel._apply_filters_and_render(reset_scroll=False)

    assert [item.name for item in panel._filtered_records] == ["One"]
