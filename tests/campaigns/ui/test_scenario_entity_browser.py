import importlib.util
import sys
import types
from pathlib import Path


class _DummyWidget:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

    def grid(self, *args, **kwargs):
        return None

    def pack(self, *args, **kwargs):
        return None

    def place(self, *args, **kwargs):
        return None

    def bind(self, *args, **kwargs):
        return None

    def after_idle(self, callback, *args, **kwargs):
        return callback(*args, **kwargs)

    def grid_columnconfigure(self, *args, **kwargs):
        return None

    def grid_rowconfigure(self, *args, **kwargs):
        return None

    def winfo_children(self):
        return []


for package_name in (
    "modules",
    "modules.campaigns",
    "modules.campaigns.ui",
    "modules.campaigns.ui.graphical_display",
    "modules.campaigns.ui.graphical_display.components",
    "modules.campaigns.ui.graphical_display.components.scenario_entities",
):
    sys.modules.setdefault(package_name, types.ModuleType(package_name))

sys.modules["customtkinter"] = types.SimpleNamespace(
    CTkFrame=_DummyWidget,
    CTkLabel=_DummyWidget,
    CTkButton=_DummyWidget,
    CTkScrollableFrame=_DummyWidget,
    CTkFont=lambda *args, **kwargs: ("font", args, kwargs),
)
sys.modules["modules.scenarios.gm_screen.dashboard.styles.dashboard_theme"] = types.SimpleNamespace(
    DASHBOARD_THEME=types.SimpleNamespace(text_primary="#fff", text_secondary="#ccc")
)
sys.modules["modules.campaigns.ui.graphical_display.data"] = types.SimpleNamespace(
    ScenarioEntityLink=object,
)

MODULE_PATH = Path("modules/campaigns/ui/graphical_display/components/scenario_entities/browser.py")
spec = importlib.util.spec_from_file_location(
    "modules.campaigns.ui.graphical_display.components.scenario_entities.browser",
    MODULE_PATH,
)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
sys.modules[spec.name] = module
spec.loader.exec_module(module)

ScenarioEntityBrowser = module.ScenarioEntityBrowser
group_scenario_entities = module.group_scenario_entities


class _Link:
    def __init__(self, entity_type: str, name: str):
        self.entity_type = entity_type
        self.name = name


def test_group_scenario_entities_orders_and_deduplicates_links():
    groups = group_scenario_entities([
        _Link("NPCs", "Mara"),
        _Link("Places", "The Gloam Market"),
        _Link("Villains", "The Hollow King"),
        _Link("NPCs", "Mara"),
        _Link("NPCs", "Vey"),
    ])

    assert groups == [
        {"entity_type": "Villains", "entities": ["The Hollow King"]},
        {"entity_type": "NPCs", "entities": ["Mara", "Vey"]},
        {"entity_type": "Places", "entities": ["The Gloam Market"]},
    ]


def test_scenario_entity_browser_renders_without_links():
    ScenarioEntityBrowser(None, scenario_title="Moonlit Wake", links=[], on_open_entity=lambda *_args: None)
