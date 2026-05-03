from __future__ import annotations

from app.onboarding.tour_engine import TourEngine
from app.onboarding.tour_models import TourPlacement, TourStep


class _FakeRoot:
    def bind(self, *_args, **_kwargs):
        return "bind-id"

    def update_idletasks(self):
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


def test_unavailable_widget_is_skipped_and_notified():
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

    assert engine.current_step == steps[1]
    assert notifications
