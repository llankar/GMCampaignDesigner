from types import SimpleNamespace

from modules.scenarios.gm_table.drag_controller import GMTableDragController
from modules.scenarios.gm_table import window_hit_testing as hit_testing
from modules.scenarios.gm_table.window_hit_testing import ScreenBounds


def test_screen_bounds_uses_exclusive_edges():
    bounds = ScreenBounds(x=100, y=200, width=50, height=25)

    assert bounds.contains(100, 200)
    assert bounds.contains(149, 224)
    assert not bounds.contains(150, 224)
    assert not bounds.contains(149, 225)


def test_map_tool_hit_testing_ignores_closed_or_minimized_maptool(monkeypatch):
    monkeypatch.setattr(
        hit_testing,
        "widget_screen_bounds",
        lambda widget: ScreenBounds(10, 20, 100, 80),
    )
    records = [
        {
            "definition": SimpleNamespace(kind="map_tool"),
            "panel": object(),
            "layout_mode": "minimized",
        },
        {
            "definition": SimpleNamespace(kind="note"),
            "panel": object(),
            "layout_mode": "floating",
        },
    ]

    assert not hit_testing.point_inside_map_tool(25, 30, records)


def test_map_tool_hit_testing_matches_visible_maptool(monkeypatch):
    monkeypatch.setattr(
        hit_testing,
        "widget_screen_bounds",
        lambda widget: ScreenBounds(10, 20, 100, 80),
    )
    records = [
        {
            "definition": SimpleNamespace(kind="map_tool"),
            "panel": object(),
            "layout_mode": "floating",
        }
    ]

    assert hit_testing.point_inside_map_tool(25, 30, records)
    assert not hit_testing.point_inside_map_tool(125, 30, records)


def test_drag_controller_blocks_middle_drag_inside_maptool(monkeypatch):
    monkeypatch.setattr(
        "modules.scenarios.gm_table.drag_controller.pointer_screen_position",
        lambda event: (42, 84),
    )
    controller = GMTableDragController(
        should_block_middle_drag=lambda screen_x, screen_y: (screen_x, screen_y) == (42, 84)
    )

    assert not controller.allows_middle_drag_start(SimpleNamespace())


def test_drag_controller_allows_middle_drag_when_maptool_unavailable(monkeypatch):
    monkeypatch.setattr(
        "modules.scenarios.gm_table.drag_controller.pointer_screen_position",
        lambda event: (42, 84),
    )
    controller = GMTableDragController(should_block_middle_drag=lambda _x, _y: False)

    assert controller.allows_middle_drag_start(SimpleNamespace())


def test_map_tool_hit_testing_matches_standalone_maptool_window(monkeypatch):
    map_tool_window = object()

    def _bounds(widget):
        if widget is map_tool_window:
            return ScreenBounds(20, 30, 60, 40)
        return None

    monkeypatch.setattr(hit_testing, "widget_screen_bounds", _bounds)

    assert hit_testing.point_inside_map_tool(25, 35, [], map_tool_window=map_tool_window)
    assert not hit_testing.point_inside_map_tool(5, 35, [], map_tool_window=map_tool_window)
