import importlib.util
import sys
import types
from pathlib import Path


MODULE_PATH = Path("modules/campaigns/ui/graphical_display/panel.py")


class _DummyWidget:
    def __init__(self, *args, **kwargs):
        pass

    def __call__(self, *args, **kwargs):
        return None

    def grid(self, *args, **kwargs):
        return None

    def pack(self, *args, **kwargs):
        return None

    def place(self, *args, **kwargs):
        return None

    def bind(self, *args, **kwargs):
        return None

    def configure(self, *args, **kwargs):
        return None

    def destroy(self):
        return None

    def grid_columnconfigure(self, *args, **kwargs):
        return None

    def grid_rowconfigure(self, *args, **kwargs):
        return None

    def winfo_children(self):
        return []

    def winfo_toplevel(self):
        return self

    def after(self, *args, **kwargs):
        return None

    def __getattr__(self, _name):
        return self._return_none

    def _return_none(self, *args, **kwargs):
        return None


def _stub_package(name: str) -> None:
    module = types.ModuleType(name)
    module.__path__ = []
    sys.modules.setdefault(name, module)


_stub_package("modules")
_stub_package("modules.campaigns")
_stub_package("modules.campaigns.ui")
_stub_package("modules.campaigns.ui.graphical_display")


dummy_ctk = types.SimpleNamespace(
    CTkFrame=_DummyWidget,
    CTkLabel=_DummyWidget,
    CTkButton=_DummyWidget,
    CTkOptionMenu=_DummyWidget,
    CTkScrollableFrame=_DummyWidget,
    CTkFont=lambda *args, **kwargs: None,
)
sys.modules.setdefault("customtkinter", dummy_ctk)
sys.modules.setdefault(
    "modules.generic.entity_detail_factory",
    types.SimpleNamespace(open_entity_tab=lambda *args, **kwargs: None),
)
sys.modules.setdefault(
    "modules.generic.generic_model_wrapper",
    types.SimpleNamespace(GenericModelWrapper=lambda *args, **kwargs: None),
)
sys.modules.setdefault(
    "modules.scenarios.gm_screen.dashboard.widgets.arc_display.arc_momentum_meter",
    types.SimpleNamespace(ArcMomentumMeter=_DummyWidget),
)
sys.modules.setdefault(
    "modules.scenarios.gm_screen.dashboard.styles.dashboard_theme",
    types.SimpleNamespace(
        DASHBOARD_THEME=types.SimpleNamespace(
            panel_bg="#000",
            panel_alt_bg="#111",
            text_primary="#fff",
            text_secondary="#ccc",
            input_bg="#222",
            input_button="#333",
            input_hover="#444",
            card_bg="#101010",
            button_hover="#555",
            accent="#666",
            accent_hover="#777",
        )
    ),
)
sys.modules.setdefault(
    "modules.campaigns.ui.graphical_display.components",
    types.SimpleNamespace(ArcSelectorStrip=_DummyWidget, ScenarioSelectorStrip=_DummyWidget, ScenarioSpotlight=_DummyWidget),
)
sys.modules.setdefault(
    "modules.campaigns.ui.graphical_display.data",
    types.SimpleNamespace(CampaignGraphArc=dict, CampaignGraphPayload=dict, build_campaign_graph_payload=lambda *a, **k: None, build_campaign_option_index=lambda *a, **k: ([], {})),
)

spec = importlib.util.spec_from_file_location("modules.campaigns.ui.graphical_display.panel", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = module
spec.loader.exec_module(module)
CampaignGraphPanel = module.CampaignGraphPanel


class _Arc:
    def __init__(self, scenarios):
        self.scenarios = scenarios


class _Payload:
    def __init__(self, arcs):
        self.arcs = arcs


def _make_panel_with_payload(payload):
    panel = CampaignGraphPanel.__new__(CampaignGraphPanel)
    panel._selected_campaign = payload
    panel._selected_arc_index = 0
    panel._selected_scenario_index = 0
    panel._refresh_arc_zone_calls = 0
    panel._refresh_scenario_zone_calls = 0

    panel._refresh_arc_zone = lambda: setattr(panel, "_refresh_arc_zone_calls", panel._refresh_arc_zone_calls + 1)
    panel._refresh_scenario_zone = lambda: setattr(panel, "_refresh_scenario_zone_calls", panel._refresh_scenario_zone_calls + 1)
    return panel


def test_select_arc_refreshes_arc_and_resets_scenario_index():
    panel = _make_panel_with_payload(_Payload([_Arc([1, 2]), _Arc([3])]))
    panel._selected_scenario_index = 1

    CampaignGraphPanel._select_arc(panel, 1)

    assert panel._selected_arc_index == 1
    assert panel._selected_scenario_index == 0
    assert panel._refresh_arc_zone_calls == 1
    assert panel._refresh_scenario_zone_calls == 0


def test_select_scenario_refreshes_only_scenario_zone():
    panel = _make_panel_with_payload(_Payload([_Arc([1, 2, 3])]))

    CampaignGraphPanel._select_scenario(panel, 2)

    assert panel._selected_arc_index == 0
    assert panel._selected_scenario_index == 2
    assert panel._refresh_arc_zone_calls == 0
    assert panel._refresh_scenario_zone_calls == 1
