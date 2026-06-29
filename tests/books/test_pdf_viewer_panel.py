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
