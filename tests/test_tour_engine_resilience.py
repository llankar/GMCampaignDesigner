from __future__ import annotations

import time

from app.onboarding.tour_engine import TourEngine
from app.onboarding.tour_models import TourPlacement, TourStep


class _FakeRoot:
    def __init__(self):
        self.idle_updates = 0

    def bind(self, *_args, **_kwargs):
        return "bind-id"

    def update_idletasks(self):
        self.idle_updates += 1
        return None


class _FakeWidget:
    def __init__(self, mapped: bool = True, manager: str = "grid", viewable: bool = True):
        self._mapped = mapped
        self._manager = manager
        self._viewable = viewable

    def winfo_exists(self):
        return True

    def winfo_manager(self):
        return self._manager

    def winfo_ismapped(self):
        return self._mapped

    def winfo_viewable(self):
        return self._viewable

    def update_idletasks(self):
        return None


def test_before_hook_can_prepare_layout_before_resolution():
    root = _FakeRoot()
    registry = {"screen:btn": None}

    def resolver(screen: str, key: str):
        return registry.get(f"{screen}:{key}")

    def before(_step: TourStep):
        registry["home:btn"] = _FakeWidget()

    step = TourStep(
        id="s1",
        screen="home",
        target_widget_key="btn",
        title="t",
        description="d",
        placement=TourPlacement.BOTTOM,
        before_hook=before,
    )
    engine = TourEngine(root, {"tour": [step]}, resolver, screen_resolver=lambda: "home")
    engine.start("tour")

    assert engine.current_step == step


def test_unavailable_widget_stops_start_without_advancing():
    root = _FakeRoot()
    notifications: list[str] = []

    steps = [
        TourStep("s1", "home", "hidden", "a", "b"),
        TourStep("s2", "home", "visible", "c", "d"),
    ]

    def resolver(_screen: str, key: str):
        if key == "visible":
            return _FakeWidget()
        return _FakeWidget(mapped=False)

    engine = TourEngine(
        root,
        {"tour": steps},
        resolver,
        screen_resolver=lambda: "home",
        user_notifier=notifications.append,
        resolution_timeout_seconds=0.01,
    )
    engine.start("tour")

    assert engine.current_step is None
    assert notifications


def test_start_waits_for_screen_to_become_active_before_notifying():
    root = _FakeRoot()
    notifications: list[str] = []
    step = TourStep("s1", "campaign_builder", "name", "a", "b")

    def screen_resolver():
        if root.idle_updates:
            return "campaign_builder"
        return "main_window"

    engine = TourEngine(
        root,
        {"tour": [step]},
        lambda _screen, _key: _FakeWidget(),
        screen_resolver=screen_resolver,
        user_notifier=notifications.append,
        resolution_timeout_seconds=0.2,
    )
    engine.start("tour")

    assert engine.current_step == step
    assert notifications == []


def test_inactive_screen_timeout_is_bounded_and_skips_widget_resolution():
    root = _FakeRoot()
    notifications: list[str] = []
    widget_resolution_calls = 0
    step = TourStep("s1", "campaign_builder", "name", "a", "b")

    def resolver(_screen: str, _key: str):
        nonlocal widget_resolution_calls
        widget_resolution_calls += 1
        return _FakeWidget()

    engine = TourEngine(
        root,
        {"tour": [step]},
        resolver,
        screen_resolver=lambda: "main_window",
        user_notifier=notifications.append,
        resolution_timeout_seconds=0.01,
    )

    started_at = time.monotonic()
    engine.start("tour")
    elapsed = time.monotonic() - started_at

    assert elapsed < 0.1
    assert engine.current_step is None
    assert widget_resolution_calls == 0
    assert notifications == ["Unable to show guided tour step 's1': screen 'campaign_builder' is not active."]


def test_failed_advance_reports_only_first_unresolved_step():
    root = _FakeRoot()
    notifications: list[str] = []
    steps = [
        TourStep("s1", "campaign_builder", "name", "a", "b"),
        TourStep("s2", "campaign_builder", "summary", "c", "d"),
        TourStep("s3", "campaign_builder", "objective", "e", "f"),
    ]

    engine = TourEngine(
        root,
        {"tour": steps},
        lambda _screen, _key: _FakeWidget(),
        screen_resolver=lambda: "main_window",
        user_notifier=notifications.append,
        resolution_timeout_seconds=0.01,
    )

    engine.start("tour")

    assert engine.current_step is None
    assert notifications == ["Unable to show guided tour step 's1': screen 'campaign_builder' is not active."]


def test_failed_start_does_not_advance_to_later_distinct_unresolved_target():
    root = _FakeRoot()
    notifications: list[str] = []
    steps = [
        TourStep("s1", "campaign_builder", "name", "a", "b"),
        TourStep("s2", "scenario_builder", "title", "c", "d"),
    ]

    engine = TourEngine(
        root,
        {"tour": steps},
        lambda _screen, _key: _FakeWidget(),
        screen_resolver=lambda: "main_window",
        user_notifier=notifications.append,
        resolution_timeout_seconds=0.01,
    )

    engine.start("tour")

    assert engine.current_step is None
    assert notifications == [
        "Unable to show guided tour step 's1': screen 'campaign_builder' is not active.",
    ]


def test_failed_next_keeps_current_step_instead_of_skipping_to_step_two():
    root = _FakeRoot()
    notifications: list[str] = []
    steps = [
        TourStep("s1", "home", "visible", "a", "b"),
        TourStep("s2", "campaign_builder", "name", "c", "d"),
        TourStep("s3", "home", "also_visible", "e", "f"),
    ]

    engine = TourEngine(
        root,
        {"tour": steps},
        lambda _screen, _key: _FakeWidget(),
        screen_resolver=lambda: "home",
        user_notifier=notifications.append,
        resolution_timeout_seconds=0.01,
    )

    engine.start("tour")
    engine.next_step()

    assert engine.current_step == steps[0]
    assert notifications == ["Unable to show guided tour step 's2': screen 'campaign_builder' is not active."]


def test_on_stop_runs_once_when_tour_stops():
    root = _FakeRoot()
    stop_calls = 0
    step = TourStep("s1", "home", "visible", "a", "b")

    def on_stop():
        nonlocal stop_calls
        stop_calls += 1

    engine = TourEngine(
        root,
        {"tour": [step]},
        lambda _screen, _key: _FakeWidget(),
        screen_resolver=lambda: "home",
        on_stop=on_stop,
    )

    engine.start("tour")
    engine.next_step()
    engine.stop()

    assert stop_calls == 1
