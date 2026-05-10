"""Regression tests for shared Tk display text guards."""
from __future__ import annotations

from modules.helpers.tk_text_safety import ELLIPSIS, safe_display_list, safe_display_text


def test_safe_display_text_truncates_huge_values_for_tk_labels() -> None:
    """Huge imported blobs should be visibly truncated before reaching Tk."""

    result = safe_display_text("x" * 100, max_chars=12)

    assert len(result) == 12
    assert result.endswith(ELLIPSIS)


def test_safe_display_list_bounds_items_and_item_length() -> None:
    """Lists rendered in menus/selectors should be capped in size and length."""

    result = safe_display_list(["a" * 20, "b" * 20, "c" * 20], max_items=2, item_max_chars=8)

    assert result == [f"aaaaaa {ELLIPSIS}", f"bbbbbb {ELLIPSIS}"]
