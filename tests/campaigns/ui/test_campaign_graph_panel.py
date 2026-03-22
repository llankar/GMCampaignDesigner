import importlib.util
import sys
import types
from pathlib import Path


class _DummyWidget:
    def __init__(self, *args, **kwargs):
        self._children = []

    def grid(self, *args, **kwargs):
        return None

    def pack(self, *args, **kwargs):
        return None

    def place(self, *args, **kwargs):
        return None

    def grid_columnconfigure(self, *args, **kwargs):
        return None

    def grid_rowconfigure(self, *args, **kwargs):
        return None

    def grid_propagate(self, *args, **kwargs):
        return None

    def configure(self, *args, **kwargs):
        return None

    def bind(self, *args, **kwargs):
        return None

    def after(self, *args, **kwargs):
        return None

    def after_idle(self, callback, *args, **kwargs):
        return callback(*args, **kwargs)

    def winfo_children(self):
        return list(self._children)


sys.modules.setdefault(
    "customtkinter",
    types.SimpleNamespace(
        CTkFrame=_DummyWidget,
        CTkLabel=_DummyWidget,
        CTkButton=_DummyWidget,
        CTkOptionMenu=_DummyWidget,
        CTkScrollableFrame=_DummyWidget,
        CTkFont=lambda *args, **kwargs: None,
    ),
)
sys.modules.setdefault(
    "modules.generic.entity_detail_factory",
    types.SimpleNamespace(open_entity_tab=lambda *args, **kwargs: None),
)
sys.modules.setdefault(
    "modules.generic.generic_model_wrapper",
    types.SimpleNamespace(GenericModelWrapper=lambda *args, **kwargs: None),
)
sys.modules.setdefault(
    "modules.scenarios.gm_screen.dashboard.styles.dashboard_theme",
    types.SimpleNamespace(DASHBOARD_THEME=types.SimpleNamespace(
        panel_bg="#000",
        panel_alt_bg="#111",
        text_primary="#fff",
        text_secondary="#ccc",
        input_bg="#222",
        input_button="#333",
        input_hover="#444",
        card_bg="#555",
        button_hover="#666",
        accent="#777",
        accent_hover="#888",
    )),
)
sys.modules.setdefault(
    "modules.scenarios.gm_screen.dashboard.widgets.arc_display.arc_momentum_meter",
    types.SimpleNamespace(ArcMomentumMeter=_DummyWidget),
)
sys.modules.setdefault(
    "modules.campaigns.ui.graphical_display.components",
    types.SimpleNamespace(ArcSelectorStrip=_DummyWidget, ScenarioSelectorStrip=_DummyWidget),
)
sys.modules.setdefault(
    "modules.campaigns.ui.graphical_display.visuals",
    types.SimpleNamespace(EntityConstellation=_DummyWidget),
)
sys.modules.setdefault(
    "modules.campaigns.ui.graphical_display.data",
    types.SimpleNamespace(
        CampaignGraphArc=object,
        CampaignGraphPayload=object,
        CampaignGraphScenario=object,
        build_campaign_graph_payload=lambda *args, **kwargs: None,
        build_campaign_option_index=lambda *args, **kwargs: ([], {}),
    ),
)

MODULE_PATH = Path("modules/campaigns/ui/graphical_display/panel.py")
spec = importlib.util.spec_from_file_location("modules.campaigns.ui.graphical_display.panel", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
sys.modules[spec.name] = module
spec.loader.exec_module(module)

CampaignGraphPanel = module.CampaignGraphPanel


class _CanvasStub:
    def __init__(self, fraction=0.0):
        self.fraction = fraction
        self.update_calls = 0
        self.moveto_calls = []

    def yview(self):
        return (self.fraction, min(self.fraction + 0.2, 1.0))

    def update_idletasks(self):
        self.update_calls += 1

    def yview_moveto(self, value):
        self.moveto_calls.append(value)
        self.fraction = value


class _ScrollStub:
    def __init__(self, canvas):
        self._parent_canvas = canvas


def _make_panel(canvas=None):
    panel = CampaignGraphPanel.__new__(CampaignGraphPanel)
    panel.scroll = _ScrollStub(canvas) if canvas is not None else None
    panel.after_idle = lambda callback, *args, **kwargs: callback(*args, **kwargs)
    return panel


def test_preserve_scroll_position_restores_canvas_fraction():
    canvas = _CanvasStub(fraction=0.62)
    panel = _make_panel(canvas)
    callback_calls = []

    panel._preserve_scroll_position(lambda: callback_calls.append("refreshed"))

    assert callback_calls == ["refreshed"]
    assert canvas.update_calls == 1
    assert canvas.moveto_calls == [0.62]


def test_scroll_to_top_moves_canvas_to_origin():
    canvas = _CanvasStub(fraction=0.48)
    panel = _make_panel(canvas)

    panel._scroll_to_top()

    assert canvas.moveto_calls == [0.0]
    assert canvas.fraction == 0.0


def test_get_scroll_fraction_returns_none_without_canvas():
    panel = _make_panel()

    assert panel._get_scroll_fraction() is None
