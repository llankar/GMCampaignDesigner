from types import SimpleNamespace

from modules.scenarios.wizard_steps.scenes.flow_canvas.view import VisualFlowCanvas
from modules.scenarios.wizard_steps.scenes.flow_canvas.viewport import ZOOM_MAX, ZOOM_MIN, clamp_zoom, compute_fit_viewport


def test_clamp_zoom_limits_range():
    assert clamp_zoom(0.01) == ZOOM_MIN
    assert clamp_zoom(99.0) == ZOOM_MAX
    assert clamp_zoom(1.25) == 1.25


def test_compute_fit_viewport_centers_and_scales_nodes():
    nodes = [
        {"x": 100, "y": 100},
        {"x": 620, "y": 320},
    ]
    viewport = compute_fit_viewport(nodes, canvas_width=1000, canvas_height=700)
    assert ZOOM_MIN <= viewport["zoom"] <= ZOOM_MAX
    assert round(viewport["zoom"], 2) == 1.15
    assert round(viewport["offset_x"], 1) == -23.0
    assert round(viewport["offset_y"], 1) == 58.0


def test_zoom_around_cursor_keeps_world_anchor_and_clamps():
    rendered = {"count": 0}
    stub = SimpleNamespace(
        _zoom=2.45,
        _offset_x=50,
        _offset_y=25,
        render=lambda: rendered.__setitem__("count", rendered["count"] + 1),
    )
    stub._screen_to_world = lambda x, y: VisualFlowCanvas._screen_to_world(stub, x, y)

    before_world = VisualFlowCanvas._screen_to_world(stub, 400, 300)
    VisualFlowCanvas._zoom_around_screen_point(stub, 400, 300, factor=1.1)
    after_world = VisualFlowCanvas._screen_to_world(stub, 400, 300)

    assert stub._zoom == ZOOM_MAX
    assert abs(before_world[0] - after_world[0]) <= 0.1
    assert abs(before_world[1] - after_world[1]) <= 0.2
    assert rendered["count"] == 1
