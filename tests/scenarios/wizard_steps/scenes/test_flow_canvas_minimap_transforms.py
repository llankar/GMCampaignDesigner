from types import SimpleNamespace

from modules.scenarios.wizard_steps.scenes.flow_canvas.minimap import minimap_to_world, world_to_minimap
from modules.scenarios.wizard_steps.scenes.flow_canvas.view import VisualFlowCanvas


def test_world_to_minimap_and_back_round_trip():
    world_bounds = (100.0, 50.0, 500.0, 250.0)
    minimap_bounds = (20.0, 30.0, 180.0, 130.0)

    mini_x, mini_y = world_to_minimap(300.0, 150.0, world_bounds=world_bounds, minimap_bounds=minimap_bounds)
    world_x, world_y = minimap_to_world(mini_x, mini_y, world_bounds=world_bounds, minimap_bounds=minimap_bounds)

    assert world_x == 300.0
    assert world_y == 150.0


def test_screen_world_transforms_round_trip_on_canvas_viewport_state():
    stub = SimpleNamespace(_zoom=1.5, _offset_x=240, _offset_y=-70)

    world_x, world_y = VisualFlowCanvas._screen_to_world(stub, 510, 305)
    screen_x, screen_y = VisualFlowCanvas._world_to_screen(stub, world_x, world_y)

    assert screen_x == 510
    assert screen_y == 305


def test_minimap_recenter_updates_offsets_for_viewport_center():
    class _CanvasStub:
        @staticmethod
        def winfo_width():
            return 800

        @staticmethod
        def winfo_height():
            return 600

    state = {"rendered": 0}
    stub = SimpleNamespace(
        _zoom=1.0,
        _offset_x=0,
        _offset_y=0,
        canvas=_CanvasStub(),
        _minimap_projection={
            "world_bounds": (0.0, 0.0, 1000.0, 1000.0),
            "minimap_bounds": (20.0, 20.0, 180.0, 180.0),
        },
    )
    stub.render = lambda: state.__setitem__("rendered", state["rendered"] + 1)

    VisualFlowCanvas._apply_minimap_recenter(stub, 100, 100)

    assert stub._offset_x == -100
    assert stub._offset_y == -200
    assert state["rendered"] == 1
