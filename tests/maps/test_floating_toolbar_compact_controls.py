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


def test_shape_selector_stacks_shape_buttons_vertically():
    import inspect

    from modules.maps.views.floating_toolbar.shape_selector import ShapeIconSelector

    source = inspect.getsource(ShapeIconSelector._build_buttons)

    assert 'button.pack(side="top"' in source
    assert 'button.pack(side="left"' not in source


def test_marker_type_filter_moved_from_floating_palette_to_top_toolbar():
    import inspect

    from modules.maps.views import floating_drawing_toolbar, toolbar_view

    floating_source = inspect.getsource(floating_drawing_toolbar._build_floating_drawing_toolbar)
    toolbar_source = inspect.getsource(toolbar_view._build_toolbar)

    assert 'Marker Type' not in floating_source
    assert 'MARKER_TYPE_FILTER_LABELS' in toolbar_source
    assert 'token_section = _create_collapsible_section(toolbar, "Tokens")' in toolbar_source


def test_floating_toolbar_layout_helpers_center_content():
    import inspect

    from modules.maps.views.floating_toolbar import layout

    layout_source = inspect.getsource(layout)

    assert 'anchor="center"' in layout_source
    assert 'anchor="w"' not in layout_source
    assert 'fill="x", padx=5' in layout_source


def test_slim_option_menu_centers_display_text():
    import inspect

    from modules.maps.views.floating_toolbar import slim_option_menu

    source = inspect.getsource(slim_option_menu.hide_option_menu_arrow)
    label_source = inspect.getsource(slim_option_menu._expand_text_label)

    assert 'anchor="center"' in source
    assert 'label.configure(anchor="center")' in label_source


def test_floating_toolbar_dynamic_controls_repack_centered():
    from pathlib import Path

    source = Path("modules/maps/controllers/display_map_controller.py").read_text()
    visibility_source = source.split("def _update_shape_controls_visibility", 1)[1].split(
        "# Method assignments", 1
    )[0]

    assert 'anchor="center"' in visibility_source
    assert 'anchor="w"' not in visibility_source
