"""Tests for compact floating map toolbar sizing helpers."""

from modules.maps.views.floating_toolbar.compact_widths import (
    CONTROL_MIN_WIDTH,
    width_for_display_text,
)


def test_width_for_display_text_uses_minimum_for_empty_values():
    assert width_for_display_text("") == CONTROL_MIN_WIDTH
    assert width_for_display_text(None) == CONTROL_MIN_WIDTH


def test_width_for_display_text_grows_with_displayed_text():
    short_width = width_for_display_text("16")
    medium_width = width_for_display_text("Token")
    long_width = width_for_display_text("Border Only")

    assert short_width == CONTROL_MIN_WIDTH
    assert medium_width > short_width
    assert long_width > medium_width


def test_brush_shape_handler_accepts_oval_label():
    from modules.maps.views.toolbar_view import _on_brush_shape_change

    panel = type("Panel", (), {})()
    _on_brush_shape_change(panel, "Oval")

    assert panel.brush_shape == "circle"
