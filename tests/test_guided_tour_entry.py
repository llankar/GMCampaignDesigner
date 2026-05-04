from app.ui.help.guided_tour_entry import GuidedTourLauncher


def test_launcher_starts_when_default_tour_exists(monkeypatch):
    calls = {}

    class FakeEngine:
        def __init__(self, *_args, **kwargs):
            calls["created"] = True
            calls["on_stop"] = kwargs.get("on_stop")
            self._tour_id = None

        def start(self, tour_id):
            calls["started"] = tour_id
            self._tour_id = tour_id

    monkeypatch.setattr("app.ui.help.guided_tour_entry.TourEngine", FakeEngine)
    monkeypatch.setattr("app.ui.help.guided_tour_entry.build_tour_registry", lambda: {"new_gm_mvp": []})

    launcher = GuidedTourLauncher()
    ok = launcher.launch_guided_tour(object(), {}, lambda: "main_window")

    assert ok is True
    assert calls["started"] == "new_gm_mvp"


def test_launcher_passes_on_stop_to_tour_engine(monkeypatch):
    calls = {}
    on_stop = object()

    class FakeEngine:
        def __init__(self, *_args, **kwargs):
            calls["on_stop"] = kwargs.get("on_stop")
            self._tour_id = None

        def start(self, tour_id):
            self._tour_id = tour_id

    monkeypatch.setattr("app.ui.help.guided_tour_entry.TourEngine", FakeEngine)
    monkeypatch.setattr("app.ui.help.guided_tour_entry.build_tour_registry", lambda: {"new_gm_mvp": []})

    launcher = GuidedTourLauncher()
    ok = launcher.launch_guided_tour(object(), {}, lambda: "main_window", on_stop=on_stop)

    assert ok is True
    assert calls["on_stop"] is on_stop


def test_launcher_warns_when_default_tour_missing(monkeypatch):
    warned = {}
    monkeypatch.setattr("app.ui.help.guided_tour_entry.build_tour_registry", lambda: {})
    monkeypatch.setattr("app.ui.help.guided_tour_entry.messagebox.showwarning", lambda title, msg: warned.update({"title": title, "msg": msg}))

    launcher = GuidedTourLauncher()
    ok = launcher.launch_guided_tour(object(), {}, lambda: "main_window")

    assert ok is False
    assert warned["title"] == "Guided Tour"
