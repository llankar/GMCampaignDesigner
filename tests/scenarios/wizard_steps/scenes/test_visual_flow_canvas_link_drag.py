from types import SimpleNamespace

from modules.scenarios.wizard_steps.scenes.flow_canvas.view import VisualFlowCanvas


class _CanvasStub:
    def __init__(self, tags=()):
        self._tags = tags

    def find_withtag(self, tag):
        return (1,) if tag == "current" and self._tags else ()

    def gettags(self, _item):
        return self._tags

    def delete(self, _item):
        return None


class _ModelStub:
    def __init__(self):
        self.payload = {
            "nodes": [
                {"id": "a", "x": 0, "y": 0},
                {"id": "b", "x": 220, "y": 0},
            ],
            "links": [],
        }


def _make_canvas_stub(current_tags=()):
    state = {"changed": 0, "rendered": 0, "selected": None, "edited": None}
    obj = SimpleNamespace(
        _drag_link_source="a",
        _drag_link_preview_item=None,
        model=_ModelStub(),
        canvas=_CanvasStub(current_tags),
    )
    obj._clear_link_preview = lambda: None
    obj._screen_to_world = lambda x, y: (x, y)
    obj._resolve_link_target_from_geometry = lambda source_id, sx, sy: VisualFlowCanvas._resolve_link_target_from_geometry(obj, source_id, sx, sy)
    obj.select_link = lambda link_id: state.__setitem__("selected", link_id)
    obj._emit_change = lambda: state.__setitem__("changed", state["changed"] + 1)
    obj.render = lambda: state.__setitem__("rendered", state["rendered"] + 1)
    obj._edit_link = lambda link_id: state.__setitem__("edited", link_id)
    return obj, state


def test_complete_link_drag_creates_link_for_valid_geometry_target():
    obj, state = _make_canvas_stub()

    VisualFlowCanvas._complete_link_drag(obj, SimpleNamespace(x=230, y=10))

    assert len(obj.model.payload["links"]) == 1
    created = obj.model.payload["links"][0]
    assert created["source"] == "a"
    assert created["target"] == "b"
    assert state["selected"] == created["id"]
    assert state["edited"] == created["id"]
    assert state["changed"] == 1


def test_complete_link_drag_rejects_invalid_target_and_cancels():
    obj, state = _make_canvas_stub()

    VisualFlowCanvas._complete_link_drag(obj, SimpleNamespace(x=1000, y=1000))

    assert obj.model.payload["links"] == []
    assert state["selected"] is None
    assert state["edited"] is None
    assert state["changed"] == 0


def test_complete_link_drag_rejects_self_link():
    obj, state = _make_canvas_stub(current_tags=("node", "a"))

    VisualFlowCanvas._complete_link_drag(obj, SimpleNamespace(x=10, y=10))

    assert obj.model.payload["links"] == []
    assert state["selected"] is None
    assert state["edited"] is None
    assert state["changed"] == 0
