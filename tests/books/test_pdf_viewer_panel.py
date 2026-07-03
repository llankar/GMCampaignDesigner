"""Headless-friendly tests for PDFViewerFrame logic."""
from __future__ import annotations
from modules.books.pdf_viewer_panel import PDFViewerFrame


def _viewer():
    viewer = PDFViewerFrame.__new__(PDFViewerFrame)
    viewer.page_count = 10
    viewer.current_page = 1
    viewer.zoom = 1.25
    viewer.pdf_path = "rules.pdf"
    viewer.attachment_path = "rules.pdf"
    viewer.title = "Rules"
    viewer.search_query = ""
    return viewer


def test_pdf_viewer_go_to_page_clamps_to_page_count() -> None:
    viewer = _viewer()
    assert PDFViewerFrame._clamp_page(viewer, 99) == 10
    assert PDFViewerFrame._clamp_page(viewer, -2) == 1


def test_pdf_viewer_adjust_zoom_clamps_between_min_and_max() -> None:
    viewer = _viewer()
    assert PDFViewerFrame._clamp_zoom(viewer, 99) == PDFViewerFrame.MAX_ZOOM
    assert PDFViewerFrame._clamp_zoom(viewer, 0.01) == PDFViewerFrame.MIN_ZOOM


def test_pdf_viewer_get_state_returns_json_safe_payload() -> None:
    viewer = _viewer()
    state = PDFViewerFrame.get_state(viewer)
    assert state == {"pdf_path": "rules.pdf", "attachment_path": "rules.pdf", "book_title": "Rules", "current_page": 1, "zoom": 1.25, "search_query": ""}


def test_pdf_viewer_discards_stale_render_requests() -> None:
    viewer = _viewer(); viewer._render_token = 4
    assert PDFViewerFrame.discard_stale_render_for_test(viewer, 3)
    assert not PDFViewerFrame.discard_stale_render_for_test(viewer, 4)

class _FakePage:
    def __init__(self, text: str) -> None:
        self._text = text

    def get_text(self, *_args):
        return self._text


class _FakeDocument:
    def __init__(self, pages: list[str]) -> None:
        self._pages = pages

    def load_page(self, index: int) -> _FakePage:
        return _FakePage(self._pages[index])


class _FakeVar:
    def __init__(self, value: str) -> None:
        self._value = value

    def get(self) -> str:
        return self._value


class _FakeLabel:
    def __init__(self) -> None:
        self.text = ""

    def configure(self, *, text: str) -> None:
        self.text = text


def _search_viewer() -> PDFViewerFrame:
    viewer = _viewer()
    viewer._document = _FakeDocument(["Alpha start", "nothing", "alpha finish"])
    viewer.page_count = 3
    viewer._search_matches = []
    viewer._search_match_index = -1
    viewer.search_status_label = _FakeLabel()
    viewer.search_var = _FakeVar("alpha")
    viewer.go_to_page = lambda page, render=True: setattr(viewer, "current_page", page)
    viewer._changed = lambda: None
    return viewer


def test_pdf_viewer_find_next_advances_to_next_matching_page() -> None:
    viewer = _search_viewer()
    viewer.search_query = ""

    PDFViewerFrame.find_next(viewer)
    assert viewer.current_page == 1
    assert viewer.search_status_label.text == "Match 1/2"

    PDFViewerFrame.find_next(viewer)
    assert viewer.current_page == 3
    assert viewer.search_status_label.text == "Match 2/2"

    PDFViewerFrame.find_next(viewer)
    assert viewer.current_page == 1
    assert viewer.search_status_label.text == "Match 1/2"


def test_pdf_viewer_find_next_rebuilds_initial_state_search() -> None:
    viewer = _search_viewer()
    viewer.search_query = "alpha"

    PDFViewerFrame.find_next(viewer)

    assert viewer.current_page == 1
    assert viewer._search_matches == [1, 3]


def test_pdf_viewer_find_next_reports_no_matches() -> None:
    viewer = _search_viewer()
    viewer.search_var = _FakeVar("missing")

    PDFViewerFrame.find_next(viewer)

    assert viewer.current_page == 1
    assert viewer.search_status_label.text == "No matches"
