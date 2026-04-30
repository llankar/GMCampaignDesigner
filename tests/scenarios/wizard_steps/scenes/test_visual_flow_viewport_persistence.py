from types import SimpleNamespace

from modules.scenarios.wizard_steps.scenes.visual_flow_planner import VisualFlowPlanner


class _ModelStub:
    def __init__(self, should_reorder=True):
        self.should_reorder = should_reorder

    def reorder_nodes(self, *_args, **_kwargs):
        return self.should_reorder


class _CanvasStub:
    def __init__(self):
        self.model = _ModelStub(True)
        self.restored = None

    def get_viewport_state(self):
        return {"x": 111, "y": -22, "zoom": 1.4}

    def set_viewport_state(self, viewport):
        self.restored = viewport


def test_reorder_relative_preserves_canvas_viewport_state():
    planner = SimpleNamespace(
        canvas=_CanvasStub(),
        _refresh_views=lambda: None,
        _on_select=lambda *_args, **_kwargs: None,
    )

    VisualFlowPlanner.reorder_node_relative(planner, "a", "b", place_after=True)

    assert planner.canvas.restored == {"x": 111, "y": -22, "zoom": 1.4}
