"""Regression tests for campaign graph navigation."""

import importlib.util
import sys
import types
from pathlib import Path


sys.modules.setdefault(
    "customtkinter",
    types.SimpleNamespace(
        CTkFrame=object,
        CTkLabel=object,
        CTkButton=object,
        CTkScrollbar=object,
        CTkFont=lambda *args, **kwargs: None,
    ),
)
sys.modules.setdefault(
    "modules.scenarios.gm_screen.dashboard.styles.dashboard_theme",
    types.SimpleNamespace(DASHBOARD_THEME=types.SimpleNamespace(text_primary="#fff", text_secondary="#ccc", accent="#66c0ff", accent_hover="#3399dd")),
)
sys.modules.setdefault(
    "modules.campaigns.ui.graphical_display.data",
    types.SimpleNamespace(CampaignGraphArc=object, CampaignGraphScenario=object),
)

module_path = Path("modules/campaigns/ui/graphical_display/components/navigation.py")
spec = importlib.util.spec_from_file_location("modules.campaigns.ui.graphical_display.components.navigation", module_path)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
sys.modules[spec.name] = module
spec.loader.exec_module(module)


def test_truncate_middle_preserves_start_and_end_of_long_titles():
    """Verify that truncate middle preserves start and end of long titles."""
    title = "Protéger un site PharmaCorp contre une attaque de terroristes Novatek"

    truncated = module._truncate_middle(title, 26)

    assert truncated.startswith("Protéger")
    assert truncated.endswith("Novatek")
    assert "…" in truncated
