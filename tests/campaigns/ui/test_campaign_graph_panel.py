"""Regression tests for campaign graph panel."""

import importlib.util
import sys
import types
from pathlib import Path


class _DummyWidget:
    def __init__(self, *args, **kwargs):
        """Initialize the _DummyWidget instance."""
        self._children = []
        self._configured = {}
        self._destroyed = False
        if args:
            parent = args[0]
            if hasattr(parent, "_children"):
                parent._children.append(self)

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

    def grid_propagate(self, *args, **kwargs):
        """Handle grid propagate."""
        return None

    def configure(self, *args, **kwargs):
        """Handle configure."""
        self._configured.update(kwargs)
        return None

    def bind(self, *args, **kwargs):
        """Bind the operation."""
        return None

    def after(self, *args, **kwargs):
        """Handle after."""
        return None

    def after_idle(self, callback, *args, **kwargs):
        """Handle after idle."""
        return callback(*args, **kwargs)

    def after_cancel(self, *args, **kwargs):
        """Handle after cancel."""
        return None

    def winfo_children(self):
        """Handle winfo children."""
        return [child for child in self._children if not getattr(child, "_destroyed", False)]

    def winfo_exists(self):
        """Handle winfo exists."""
        return not self._destroyed

    def destroy(self):
        """Destroy the operation."""
        self._destroyed = True


class _TextWidget(_DummyWidget):
    def __init__(self, *args, **kwargs):
        """Initialize the _TextWidget instance."""
        self.text = kwargs.get("text", "")
        super().__init__(*args, **kwargs)

    def configure(self, *args, **kwargs):
        """Handle configure."""
        if "text" in kwargs:
            self.text = kwargs["text"]
        return super().configure(*args, **kwargs)


sys.modules.setdefault(
    "customtkinter",
    types.SimpleNamespace(
        CTkFrame=_DummyWidget,
        CTkLabel=_TextWidget,
        CTkButton=_TextWidget,
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
    types.SimpleNamespace(
        CampaignOverviewHero=_DummyWidget,
        ArcSelectorStrip=_DummyWidget,
        ScenarioEntityBrowser=_DummyWidget,
        ScenarioBriefingPanel=_DummyWidget,
        ScenarioHeroStrip=_DummyWidget,
        ScenarioIdentityPanel=_DummyWidget,
        ScenarioSelectorStrip=_DummyWidget,
    ),
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
sys.modules.setdefault(
    "modules.scenarios.gm_screen_view",
    types.SimpleNamespace(GMScreenView=_DummyWidget),
)
sys.modules.setdefault(
    "modules.scenarios.gm_layout_manager",
    types.SimpleNamespace(GMScreenLayoutManager=_DummyWidget),
)
sys.modules.setdefault(
    "modules.campaigns.ui.graphical_display.services",
    types.SimpleNamespace(
        open_scenario_in_embedded_gm_screen=lambda widget, scenario_name, fallback: widget.winfo_toplevel().open_gm_screen(show_empty_message=True, scenario_name=scenario_name)
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
        """Initialize the _CanvasStub instance."""
        self.fraction = fraction
        self.update_calls = 0
        self.moveto_calls = []

    def yview(self):
        """Handle yview."""
        return (self.fraction, min(self.fraction + 0.2, 1.0))

    def update_idletasks(self):
        """Update idletasks."""
        self.update_calls += 1

    def yview_moveto(self, value):
        """Handle yview moveto."""
        self.moveto_calls.append(value)
        self.fraction = value


class _ScrollStub:
    def __init__(self, canvas):
        """Initialize the _ScrollStub instance."""
        self._parent_canvas = canvas


class _SelectorStripStub(_DummyWidget):
    created = 0

    def __init__(self, parent, *, scenarios, selected_index, on_select):
        """Initialize the _SelectorStripStub instance."""
        type(self).created += 1
        super().__init__(parent)
        self.scenarios = list(scenarios)
        self.selected_index = selected_index
        self.on_select = on_select
        self.selected_updates = []
        self.scenario_updates = []

    def set_selected_index(self, index):
        """Handle set selected index."""
        self.selected_index = index
        self.selected_updates.append(index)

    def set_scenarios(self, scenarios, selected_index):
        """Handle set scenarios."""
        self.scenarios = list(scenarios)
        self.selected_index = selected_index
        self.scenario_updates.append((len(self.scenarios), selected_index))


class _CountingWidget(_DummyWidget):
    created = 0

    def __init__(self, parent, *args, **kwargs):
        """Initialize the _CountingWidget instance."""
        type(self).created += 1
        super().__init__(parent, *args, **kwargs)


class _ScenarioEntityBrowserStub(_CountingWidget):
    pass


class _ScenarioHeroStripStub(_CountingWidget):
    pass


class _ScenarioIdentityPanelStub(_CountingWidget):
    pass


class _ScenarioBriefingPanelStub(_CountingWidget):
    pass


def _make_scenario(title, *, links=0, record_exists=False):
    """Build a minimal scenario payload for panel tests."""
    entity_links = [types.SimpleNamespace(entity_type="NPCs", name=f"NPC {index}") for index in range(links)]
    return types.SimpleNamespace(
        title=title,
        summary=f"Summary for {title}",
        briefing=f"Briefing for {title}",
        objective=f"Objective for {title}",
        hook=f"Hook for {title}",
        stakes=f"Stakes for {title}",
        tags=[f"{title} tag"],
        entity_links=entity_links,
        linked_entity_count=len(entity_links),
        linked_places_count=0,
        linked_factions_count=0,
        linked_villains_count=0,
        primary_link_type="NPCs" if entity_links else "",
        scene_count=2,
        has_secrets=False,
        record_exists=record_exists,
    )


def _make_arc(name, scenarios):
    """Build a minimal arc payload for panel tests."""
    return types.SimpleNamespace(name=name, status="Planned", summary=f"Summary for {name}", objective=f"Objective for {name}", scenarios=scenarios)


def _make_panel(canvas=None):
    """Internal helper for make panel."""
    panel = CampaignGraphPanel.__new__(CampaignGraphPanel)
    panel.scroll = _ScrollStub(canvas) if canvas is not None else None
    panel.after_idle = lambda callback, *args, **kwargs: callback(*args, **kwargs)
    return panel


def test_preserve_scroll_position_restores_canvas_fraction():
    """Verify that preserve scroll position restores canvas fraction."""
    canvas = _CanvasStub(fraction=0.62)
    panel = _make_panel(canvas)
    callback_calls = []

    panel._preserve_scroll_position(lambda: callback_calls.append("refreshed"))

    assert callback_calls == ["refreshed"]
    assert canvas.update_calls == 1
    assert canvas.moveto_calls == [0.62]


def test_scroll_to_top_moves_canvas_to_origin():
    """Verify that scroll to top moves canvas to origin."""
    canvas = _CanvasStub(fraction=0.48)
    panel = _make_panel(canvas)

    panel._scroll_to_top()

    assert canvas.moveto_calls == [0.0]
    assert canvas.fraction == 0.0


def test_get_scroll_fraction_returns_none_without_canvas():
    """Verify that get scroll fraction returns none without canvas."""
    panel = _make_panel()

    assert panel._get_scroll_fraction() is None


class _HostApp:
    def __init__(self):
        """Initialize the _HostApp instance."""
        self.calls = []

    def open_gm_screen(self, **kwargs):
        """Open GM screen."""
        self.calls.append(kwargs)


def test_open_scenario_gm_screen_prefers_embedded_host(monkeypatch):
    """Verify that open scenario GM screen prefers embedded host."""
    panel = CampaignGraphPanel.__new__(CampaignGraphPanel)
    panel._scenario_items = [{"Title": "Night Run"}]
    host = _HostApp()
    panel.winfo_toplevel = lambda: host

    module.messagebox = types.SimpleNamespace(showerror=lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("unexpected error")))

    panel._open_scenario_gm_screen("Night Run")

    assert host.calls == [{"show_empty_message": True, "scenario_name": "Night Run"}]


def test_scenario_focus_updates_in_place_and_defers_sidebar(monkeypatch):
    """Verify that scenario focus updates reuse the shell and defer the sidebar."""
    _SelectorStripStub.created = 0
    _ScenarioHeroStripStub.created = 0
    _ScenarioIdentityPanelStub.created = 0
    _ScenarioBriefingPanelStub.created = 0
    _ScenarioEntityBrowserStub.created = 0

    monkeypatch.setattr(module, "ScenarioSelectorStrip", _SelectorStripStub)
    monkeypatch.setattr(module, "ScenarioHeroStrip", _ScenarioHeroStripStub)
    monkeypatch.setattr(module, "ScenarioIdentityPanel", _ScenarioIdentityPanelStub)
    monkeypatch.setattr(module, "ScenarioBriefingPanel", _ScenarioBriefingPanelStub)
    monkeypatch.setattr(module, "ScenarioEntityBrowser", _ScenarioEntityBrowserStub)
    monkeypatch.setattr(
        module,
        "ctk",
        types.SimpleNamespace(
            CTkFrame=_DummyWidget,
            CTkLabel=_TextWidget,
            CTkButton=_TextWidget,
            CTkScrollableFrame=_DummyWidget,
            CTkFont=lambda *args, **kwargs: None,
            CTkToplevel=_DummyWidget,
        ),
    )
    monkeypatch.setattr(
        module,
        "DASHBOARD_THEME",
        types.SimpleNamespace(
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
            button_fg="#999",
            accent_soft="#aaa",
            card_border="#bbb",
            arc_planned="#ccc",
            arc_active="#ddd",
            arc_complete="#eee",
        ),
    )

    scheduled = []
    canceled = []

    panel = CampaignGraphPanel.__new__(CampaignGraphPanel)
    panel._selected_campaign = types.SimpleNamespace(arcs=[])
    arc = _make_arc("Red Revelations", [_make_scenario("Moonlit Wake", links=2), _make_scenario("Catacomb Chase", links=3)])
    panel._selected_campaign.arcs = [arc]
    panel._selected_arc_index = 0
    panel._selected_scenario_index = 0
    panel._scenario_focus_container = _DummyWidget()
    panel._status_color = lambda status: f"status:{status}"
    panel._open_scenario = lambda *_args, **_kwargs: None
    panel._open_scenario_gm_screen = lambda *_args, **_kwargs: None
    panel._open_entity = lambda *_args, **_kwargs: None
    panel.after = lambda delay, callback, *args, **kwargs: scheduled.append((delay, callback, args, kwargs)) or f"job-{len(scheduled)}"
    panel.after_cancel = lambda job: canceled.append(job)

    panel._build_scenario_focus_shell(arc)

    assert _SelectorStripStub.created == 1
    assert _ScenarioHeroStripStub.created == 1
    assert _ScenarioIdentityPanelStub.created == 1
    assert _ScenarioBriefingPanelStub.created == 1
    assert _ScenarioEntityBrowserStub.created == 0
    assert panel._scenario_section is not None
    assert panel._scenario_section.winfo_exists()
    assert panel._scenario_right_stack is not None
    assert len(panel._scenario_right_stack.winfo_children()) == 2
    assert panel._scenario_prev_button.text == "← Previous"
    assert panel._scenario_next_button.text == "Next →"
    assert panel._scenario_status_label.text == "2 links"
    assert len(scheduled) == 1
    assert len(panel._scenario_sidebar_container.winfo_children()) == 1

    panel._selected_scenario_index = 1
    panel._update_selected_scenario_focus(arc)

    assert _SelectorStripStub.created == 1
    assert panel._scenario_selector_strip.selected_updates[-1] == 1
    assert canceled == ["job-1"]
    assert len(scheduled) == 2
    assert len(panel._scenario_sidebar_container.winfo_children()) == 1

    scheduled[-1][1]()

    assert _ScenarioEntityBrowserStub.created == 1
    assert len(panel._scenario_sidebar_container.winfo_children()) == 1


def test_refresh_scenario_focus_builds_initial_shell(monkeypatch):
    """Verify that the first scenario refresh builds the shell and defers the sidebar."""
    _SelectorStripStub.created = 0
    _ScenarioHeroStripStub.created = 0
    _ScenarioIdentityPanelStub.created = 0
    _ScenarioBriefingPanelStub.created = 0
    _ScenarioEntityBrowserStub.created = 0

    monkeypatch.setattr(module, "ScenarioSelectorStrip", _SelectorStripStub)
    monkeypatch.setattr(module, "ScenarioHeroStrip", _ScenarioHeroStripStub)
    monkeypatch.setattr(module, "ScenarioIdentityPanel", _ScenarioIdentityPanelStub)
    monkeypatch.setattr(module, "ScenarioBriefingPanel", _ScenarioBriefingPanelStub)
    monkeypatch.setattr(module, "ScenarioEntityBrowser", _ScenarioEntityBrowserStub)
    monkeypatch.setattr(
        module,
        "ctk",
        types.SimpleNamespace(
            CTkFrame=_DummyWidget,
            CTkLabel=_DummyWidget,
            CTkButton=_DummyWidget,
            CTkScrollableFrame=_DummyWidget,
            CTkFont=lambda *args, **kwargs: None,
            CTkToplevel=_DummyWidget,
        ),
    )
    monkeypatch.setattr(
        module,
        "DASHBOARD_THEME",
        types.SimpleNamespace(
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
            button_fg="#999",
            accent_soft="#aaa",
            card_border="#bbb",
            arc_planned="#ccc",
            arc_active="#ddd",
            arc_complete="#eee",
        ),
    )

    scheduled = []
    canceled = []

    panel = CampaignGraphPanel.__new__(CampaignGraphPanel)
    panel._selected_campaign = types.SimpleNamespace(arcs=[])
    arc = _make_arc("Red Revelations", [_make_scenario("Moonlit Wake", links=2), _make_scenario("Catacomb Chase", links=3)])
    panel._selected_campaign.arcs = [arc]
    panel._selected_arc_index = 0
    panel._selected_scenario_index = 0
    panel._scenario_focus_container = _DummyWidget()
    panel._scenario_section = None
    panel._status_color = lambda status: f"status:{status}"
    panel._open_scenario = lambda *_args, **_kwargs: None
    panel._open_scenario_gm_screen = lambda *_args, **_kwargs: None
    panel._open_entity = lambda *_args, **_kwargs: None
    panel.after = lambda delay, callback, *args, **kwargs: scheduled.append((delay, callback, args, kwargs)) or f"job-{len(scheduled)}"
    panel.after_cancel = lambda job: canceled.append(job)

    panel._refresh_scenario_focus()

    assert _SelectorStripStub.created == 1
    assert _ScenarioHeroStripStub.created == 1
    assert _ScenarioIdentityPanelStub.created == 1
    assert _ScenarioBriefingPanelStub.created == 1
    assert _ScenarioEntityBrowserStub.created == 0
    assert panel._scenario_section is not None
    assert panel._scenario_section.winfo_exists()
    assert panel._scenario_right_stack is not None
    assert len(panel._scenario_right_stack.winfo_children()) == 2
    assert len(scheduled) == 1
    assert len(panel._scenario_sidebar_container.winfo_children()) == 1

    scheduled[0][1]()

    assert _ScenarioEntityBrowserStub.created == 1
    assert canceled == []
    assert len(panel._scenario_sidebar_container.winfo_children()) == 1


def test_destroy_cancels_pending_sidebar_job(monkeypatch):
    """Verify that destroying the panel cancels deferred sidebar work."""
    panel = CampaignGraphPanel.__new__(CampaignGraphPanel)
    canceled = []
    panel._pending_sidebar_job = "job-1"
    panel.after_cancel = lambda job: canceled.append(job)

    panel.destroy()

    assert canceled == ["job-1"]
    assert panel._pending_sidebar_job is None
    assert panel._pending_sidebar_target is None
