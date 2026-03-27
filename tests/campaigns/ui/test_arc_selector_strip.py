import importlib.util
import sys
import types
from pathlib import Path

from modules.campaigns.ui.graphical_display.data import CampaignGraphArc


class _DummyFrame:
    def __init__(self, *args, **kwargs):
        self._children = []

    def after_idle(self, callback, *args, **kwargs):
        return callback(*args, **kwargs)


class _FakeCanvas:
    def __init__(self, *args, **kwargs):
        self.bound = {}
        self.configured = {}
        self.deleted = []
        self.created = []

    def pack(self, *args, **kwargs):
        return None

    def bind(self, *args, **kwargs):
        return None

    def tag_bind(self, tag, sequence, callback):
        self.bound[(tag, sequence)] = callback

    def winfo_exists(self):
        return True

    def winfo_width(self):
        return 480

    def winfo_height(self):
        return 124

    def delete(self, *args):
        self.deleted.append(args)

    def create_rectangle(self, *args, **kwargs):
        self.created.append(("rectangle", args, kwargs))

    def create_text(self, *args, **kwargs):
        self.created.append(("text", args, kwargs))

    def configure(self, **kwargs):
        self.configured.update(kwargs)


sys.modules["customtkinter"] = types.SimpleNamespace(CTkFrame=_DummyFrame)
sys.modules["modules.scenarios.gm_screen.dashboard.styles.dashboard_theme"] = types.SimpleNamespace(
    DASHBOARD_THEME=types.SimpleNamespace(text_primary="#ffffff", text_secondary="#cccccc")
)

MODULE_PATH = Path("modules/campaigns/ui/graphical_display/components/navigation.py")
spec = importlib.util.spec_from_file_location("modules.campaigns.ui.graphical_display.components.navigation", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
sys.modules[spec.name] = module
spec.loader.exec_module(module)


def test_arc_selector_strip_callbacks_accept_missing_event(monkeypatch):
    fake_canvas = _FakeCanvas()
    monkeypatch.setattr(module.tk, "Canvas", lambda *args, **kwargs: fake_canvas)

    selected = []
    strip = module.ArcSelectorStrip(
        _DummyFrame(),
        arcs=[
            CampaignGraphArc(
                name="Guild War",
                status="Planned",
                summary="Street-level pressure escalates.",
                objective="Break the syndicate",
                scenarios=[],
            )
        ],
        selected_index=0,
        on_select=selected.append,
    )

    button_cb = fake_canvas.bound[("arc:0", "<Button-1>")]
    enter_cb = fake_canvas.bound[("arc:0", "<Enter>")]
    leave_cb = fake_canvas.bound[("arc:0", "<Leave>")]

    button_cb()
    enter_cb()
    leave_cb()

    assert selected == [0]
    assert fake_canvas.configured["cursor"] == ""
    assert strip.canvas is fake_canvas
