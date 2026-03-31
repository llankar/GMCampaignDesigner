"""Regression tests for campaign graph pills."""

import importlib.util
import sys
import types
from pathlib import Path


class _DummyWidget:
    def __init__(self, *args, **kwargs):
        """Initialize the _DummyWidget instance."""
        self.args = args
        self.kwargs = kwargs

    def grid(self, *args, **kwargs):
        """Handle grid."""
        return None

    def pack(self, *args, **kwargs):
        """Pack the operation."""
        return None

    def place(self, *args, **kwargs):
        """Handle place."""
        return None

    def grid_columnconfigure(self, *args, **kwargs):
        """Handle grid columnconfigure."""
        return None

    def grid_rowconfigure(self, *args, **kwargs):
        """Handle grid rowconfigure."""
        return None


class _StrictLabel(_DummyWidget):
    def __init__(self, *args, **kwargs):
        """Initialize the _StrictLabel instance."""
        unsupported = [key for key in ("border_width", "border_color") if key in kwargs]
        if unsupported:
            raise TypeError(f"Unsupported CTkLabel arguments: {unsupported}")
        super().__init__(*args, **kwargs)


def _load_module(module_name: str, relative_path: str):
    """Load module."""
    module_path = Path(relative_path)
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


sys.modules["customtkinter"] = types.SimpleNamespace(
    CTkFrame=_DummyWidget,
    CTkLabel=_StrictLabel,
    CTkButton=_DummyWidget,
    CTkFont=lambda *args, **kwargs: ("font", args, kwargs),
)
sys.modules["modules.scenarios.gm_screen.dashboard.styles.dashboard_theme"] = types.SimpleNamespace(
    DASHBOARD_THEME=types.SimpleNamespace(
        text_primary="#fff",
        text_secondary="#ccc",
        accent="#66c0ff",
        accent_hover="#3399dd",
    )
)

for package_name in (
    "modules",
    "modules.campaigns",
    "modules.campaigns.ui",
    "modules.campaigns.ui.graphical_display",
    "modules.campaigns.ui.graphical_display.components",
):
    sys.modules.setdefault(package_name, types.ModuleType(package_name))

_load_module(
    "modules.campaigns.ui.graphical_display.components.pill",
    "modules/campaigns/ui/graphical_display/components/pill.py",
)
scenario_metrics = _load_module(
    "modules.campaigns.ui.graphical_display.components.scenario_metrics",
    "modules/campaigns/ui/graphical_display/components/scenario_metrics.py",
)
scenario_header = _load_module(
    "modules.campaigns.ui.graphical_display.components.scenario_header",
    "modules/campaigns/ui/graphical_display/components/scenario_header.py",
)


def test_scenario_tag_row_uses_frame_backed_pills():
    """Verify that scenario tag row uses frame backed pills."""
    scenario_metrics.ScenarioTagRow(None, tags=["Mystery", "Urban"], accent="#7dd3fc")


def test_scenario_hero_strip_uses_frame_backed_pills():
    """Verify that scenario hero strip uses frame backed pills."""
    scenario_header.ScenarioHeroStrip(
        None,
        title="The Hollow Crown",
        subtitle="Arc finale",
        count_chips=[("Scenes", "5"), ("Links", "9")],
        on_edit=lambda: None,
        on_open_gm_screen=lambda: None,
    )
