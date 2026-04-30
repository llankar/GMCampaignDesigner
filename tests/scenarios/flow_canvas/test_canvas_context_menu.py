import types

from modules.scenarios.wizard_steps.scenes.flow_canvas import view


class _FakeMenu:
    def __init__(self, *_args, **_kwargs):
        self.commands = []
        self.popup_args = None

    def add_command(self, label, command):
        self.commands.append({"label": label, "command": command})

    def tk_popup(self, x_root, y_root):
        self.popup_args = (x_root, y_root)


def test_canvas_menu_actions_map_to_expected_node_kinds(monkeypatch):
    captured_kinds = []
    fake_menu = _FakeMenu()

    monkeypatch.setattr(view.tk, "Menu", lambda *_args, **_kwargs: fake_menu)
    monkeypatch.setattr(view, "should_open_context_menu", lambda *_args: True)
    monkeypatch.setattr(view, "now", lambda: 10.0)

    canvas = view.VisualFlowCanvas.__new__(view.VisualFlowCanvas)
    canvas._context_press_ts = 0.0
    canvas._add_node_at = lambda _x, _y, kind: captured_kinds.append(kind)
    canvas.reset_zoom = lambda: None
    canvas.fit_view = lambda: None

    event = types.SimpleNamespace(x=100, y=200, x_root=10, y_root=20)
    canvas._canvas_menu(event)

    for command in fake_menu.commands[:7]:
        command["command"]()

    assert captured_kinds == [
        "scene",
        "objective",
        "side_objective",
        "interaction",
        "condition",
        "action",
        "note",
    ]
