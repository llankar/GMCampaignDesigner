from __future__ import annotations

from types import SimpleNamespace

import main_window


_DEFAULT_BUILDER = object()


def _make_main_window_stub(monkeypatch, *, builder=_DEFAULT_BUILDER):
    app = main_window.MainWindow.__new__(main_window.MainWindow)
    calls: list[str] = []
    resolver = object()
    if builder is _DEFAULT_BUILDER:
        builder = SimpleNamespace()

    app._tour_widget_registry = SimpleNamespace(resolver=lambda: resolver)
    app._campaign_builder_wizard = builder
    app._resolve_tour_screen = lambda: "campaign_builder"
    app.update_idletasks = lambda: calls.append("flush")

    def open_campaign_builder(*, guided_tour_active: bool = False):
        calls.append(f"open:{guided_tour_active}")
        return builder

    app.open_campaign_builder = open_campaign_builder

    captured = {}

    def fake_launch_guided_tour(root_window, widget_registry, current_screen_getter, *, on_stop=None):
        calls.append("launch")
        captured.update(
            root_window=root_window,
            widget_registry=widget_registry,
            current_screen=current_screen_getter(),
            on_stop=on_stop,
        )
        return True

    monkeypatch.setattr(main_window, "launch_guided_tour", fake_launch_guided_tour)
    return app, calls, captured, resolver, builder


def test_main_window_launch_guided_tour_opens_builder_before_start(monkeypatch):
    app, calls, captured, resolver, builder = _make_main_window_stub(monkeypatch)

    assert app.launch_guided_tour() is True

    assert calls == ["open:True", "flush", "launch"]
    assert captured == {
        "root_window": app,
        "widget_registry": resolver,
        "current_screen": "campaign_builder",
        "on_stop": app._clear_guided_tour_campaign_builder_state,
    }
    assert builder._guided_tour_active is True


def test_main_window_launch_guided_tour_stops_when_builder_fails(monkeypatch):
    app, calls, captured, _resolver, _builder = _make_main_window_stub(monkeypatch, builder=None)

    assert app.launch_guided_tour() is False

    assert calls == ["open:True"]
    assert captured == {}


def test_main_window_launch_guided_tour_clears_builder_flag_when_start_fails(monkeypatch):
    builder = SimpleNamespace(_guided_tour_active=False)
    app, calls, _captured, _resolver, _builder = _make_main_window_stub(monkeypatch, builder=builder)

    def fake_launch_guided_tour(_root_window, _widget_registry, current_screen_getter, *, on_stop=None):
        calls.append("launch")
        return False

    monkeypatch.setattr(main_window, "launch_guided_tour", fake_launch_guided_tour)

    assert app.launch_guided_tour() is False

    assert calls == ["open:True", "flush", "launch"]
    assert builder._guided_tour_active is False


def test_main_window_clears_guided_tour_flag_on_stop():
    app = main_window.MainWindow.__new__(main_window.MainWindow)
    builder = SimpleNamespace(_guided_tour_active=True)
    app._campaign_builder_wizard = builder

    app._clear_guided_tour_campaign_builder_state()

    assert builder._guided_tour_active is False


class _FakeTourWindow:
    def __init__(
        self,
        *,
        exists: bool = True,
        state: str = "normal",
        viewable: bool | None = None,
        children: list[object] | None = None,
    ):
        self.exists = exists
        self.state = state
        self.viewable = viewable
        self.children = children or []

    def winfo_exists(self):
        return self.exists

    def wm_state(self):
        return self.state

    def winfo_viewable(self):
        return True if self.viewable is None else bool(self.viewable)

    def winfo_children(self):
        return self.children


class CampaignBuilderWizard(_FakeTourWindow):
    pass


class ScenarioBuilderWizard(_FakeTourWindow):
    pass


def test_main_window_resolves_visible_campaign_builder_as_active_screen():
    app = main_window.MainWindow.__new__(main_window.MainWindow)
    app._campaign_builder_wizard = CampaignBuilderWizard()
    app.current_open_entity = None
    app.winfo_children = lambda: []

    assert app._resolve_tour_screen() == "campaign_builder"


def test_main_window_resolves_viewable_campaign_builder_as_active_even_during_state_lag():
    app = main_window.MainWindow.__new__(main_window.MainWindow)
    app._campaign_builder_wizard = CampaignBuilderWizard(state="withdrawn", viewable=True)
    app.current_open_entity = None

    assert app._resolve_tour_screen() == "campaign_builder"


def test_main_window_resolves_visible_child_dialog_before_tracked_campaign_builder():
    scenario_builder = ScenarioBuilderWizard()
    campaign_builder = CampaignBuilderWizard(children=[scenario_builder])
    app = main_window.MainWindow.__new__(main_window.MainWindow)
    app._campaign_builder_wizard = campaign_builder
    app.current_open_entity = None
    app.winfo_children = lambda: [campaign_builder]

    assert app._resolve_tour_screen() == "scenario_builder"


def test_main_window_ignores_withdrawn_campaign_builder_for_active_screen():
    app = main_window.MainWindow.__new__(main_window.MainWindow)
    app._campaign_builder_wizard = CampaignBuilderWizard(state="withdrawn", viewable=False)
    app.current_open_entity = "npcs"
    app.winfo_children = lambda: []

    assert app._resolve_tour_screen() == "entity_npcs"
