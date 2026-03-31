"""Regression tests for entity field scrollbars."""

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

    def insert(self, *args, **kwargs):
        """Handle insert."""
        return None

    def configure(self, *args, **kwargs):
        """Handle configure."""
        return None

    def grid_columnconfigure(self, *args, **kwargs):
        """Handle grid columnconfigure."""
        return None

    def grid_rowconfigure(self, *args, **kwargs):
        """Handle grid rowconfigure."""
        return None


class _TextboxRecorder(_DummyWidget):
    created_kwargs: list[dict] = []

    def __init__(self, *args, **kwargs):
        """Initialize the _TextboxRecorder instance."""
        super().__init__(*args, **kwargs)
        _TextboxRecorder.created_kwargs.append(kwargs)


def _load_module(module_name: str, path: str):
    """Load module."""
    spec = importlib.util.spec_from_file_location(module_name, Path(path))
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _ensure_packages(*package_names: str) -> None:
    """Ensure packages."""
    for package_name in package_names:
        sys.modules.setdefault(package_name, types.ModuleType(package_name))


def test_campaign_overview_panel_field_textbox_uses_scrollbars():
    """Verify that campaign overview panel field textbox uses scrollbars."""
    _ensure_packages("modules", "modules.scenarios", "modules.scenarios.gm_screen", "modules.helpers")
    sys.modules["customtkinter"] = types.SimpleNamespace(
        CTkFrame=_DummyWidget,
        CTkLabel=_DummyWidget,
        CTkButton=_DummyWidget,
        CTkOptionMenu=_DummyWidget,
        CTkScrollableFrame=_DummyWidget,
        CTkTextbox=_TextboxRecorder,
        CTkFont=lambda *args, **kwargs: ("font", args, kwargs),
    )
    sys.modules["modules.helpers.text_helpers"] = types.SimpleNamespace(coerce_text=lambda value: str(value or ""))
    sys.modules["modules.scenarios.gm_screen.campaign_entity_browser"] = types.SimpleNamespace(
        build_campaign_entity_catalog=lambda wrappers: [],
        build_option_index=lambda catalog: ([], {}),
        extract_display_fields=lambda entity_type, item: [],
        scenario_label=lambda item: "Scenario",
    )

    module = _load_module("modules.scenarios.gm_screen.campaign_overview_panel", "modules/scenarios/gm_screen/campaign_overview_panel.py")
    panel = module.CampaignOverviewPanel.__new__(module.CampaignOverviewPanel)

    _TextboxRecorder.created_kwargs.clear()
    panel._render_read_only_field(_DummyWidget(), "Long field value " * 30)

    assert _TextboxRecorder.created_kwargs
    assert _TextboxRecorder.created_kwargs[-1]["activate_scrollbars"] is True


def test_campaign_dashboard_panel_field_textbox_uses_scrollbars():
    """Verify that campaign dashboard panel field textbox uses scrollbars."""
    _ensure_packages(
        "modules",
        "modules.campaigns",
        "modules.campaigns.shared",
        "modules.scenarios",
        "modules.scenarios.gm_screen",
        "modules.scenarios.gm_screen.dashboard",
        "modules.scenarios.gm_screen.dashboard.widgets",
        "modules.scenarios.gm_screen.dashboard.search",
        "modules.scenarios.gm_screen.dashboard.session_prep",
        "modules.scenarios.gm_screen.dashboard.styles",
        "modules.exports",
    )
    sys.modules["customtkinter"] = types.SimpleNamespace(
        CTkFrame=_DummyWidget,
        CTkLabel=_DummyWidget,
        CTkButton=_DummyWidget,
        CTkOptionMenu=_DummyWidget,
        CTkEntry=_DummyWidget,
        CTkCheckBox=_DummyWidget,
        CTkScrollableFrame=_DummyWidget,
        CTkTextbox=_TextboxRecorder,
        CTkFont=lambda *args, **kwargs: ("font", args, kwargs),
    )
    sys.modules["modules.campaigns.shared.arc_parser"] = types.SimpleNamespace(coerce_arc_list=lambda raw: [])
    sys.modules["modules.scenarios.gm_screen.dashboard.widgets.campaign_arc_field"] = types.SimpleNamespace(
        CampaignArcField=_DummyWidget
    )
    sys.modules["modules.scenarios.gm_screen.dashboard.campaign_dashboard_data"] = types.SimpleNamespace(
        build_campaign_option_index=lambda catalog: ([], {}),
        extract_campaign_fields=lambda item: [],
        load_campaign_entities=lambda wrappers: [],
    )
    sys.modules["modules.scenarios.gm_screen.dashboard.search.campaign_field_search"] = types.SimpleNamespace(
        build_field_search_index=lambda fields: [],
        find_match_ranges=lambda value, query: [],
        normalize_query=lambda query: "",
    )
    sys.modules["modules.exports.session_brief"] = types.SimpleNamespace(export_session_brief=lambda **kwargs: "output.docx")
    sys.modules["modules.scenarios.gm_screen.dashboard.session_prep"] = types.SimpleNamespace(
        build_session_brief_payload=lambda **kwargs: types.SimpleNamespace(
            summary="",
            active_arcs=[],
            arc_details=[],
            dashboard_fields=[],
            gm_priority_notes=[],
        )
    )
    sys.modules["modules.scenarios.gm_screen.dashboard.session_prep.session_prep_summary"] = types.SimpleNamespace(
        build_session_prep_summary=lambda fields: types.SimpleNamespace(
            active_objectives=[],
            in_progress_arcs=[],
            critical_reminders=[],
        )
    )
    sys.modules["modules.scenarios.gm_screen.dashboard.styles.dashboard_theme"] = types.SimpleNamespace(
        DASHBOARD_THEME=types.SimpleNamespace(
            panel_bg="#000",
            panel_alt_bg="#111",
            card_bg="#222",
            card_border="#333",
            text_secondary="#ccc",
            text_primary="#fff",
            input_bg="#444",
            input_button="#555",
            input_hover="#666",
            button_fg="#777",
            button_hover="#888",
        )
    )

    module = _load_module(
        "modules.scenarios.gm_screen.dashboard.campaign_dashboard_panel",
        "modules/scenarios/gm_screen/dashboard/campaign_dashboard_panel.py",
    )
    panel = module.CampaignDashboardPanel.__new__(module.CampaignDashboardPanel)
    panel._HIGHLIGHT_BG_COLOR = "#000"
    panel._HIGHLIGHT_TEXT_COLOR = "#fff"

    _TextboxRecorder.created_kwargs.clear()
    panel._render_read_only_field(_DummyWidget(), "Long field value " * 30, query="")

    assert _TextboxRecorder.created_kwargs
    assert _TextboxRecorder.created_kwargs[-1]["activate_scrollbars"] is True
