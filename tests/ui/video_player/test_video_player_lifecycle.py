"""Headless lifecycle coverage for the second-screen video player."""

from types import SimpleNamespace

from modules.ui import video_player


class _Window:
    def __init__(self):
        self.cancelled = []
        self.destroyed = False

    def after(self, _delay, callback):
        callback_id = f"after-{id(callback)}"
        return callback_id

    def after_cancel(self, callback_id):
        self.cancelled.append(callback_id)

    def winfo_exists(self):
        return not self.destroyed

    def destroy(self):
        self.destroyed = True


def _bare_player(*, loop=True, frames=()):
    player = video_player._SecondScreenVideoPlayer.__new__(
        video_player._SecondScreenVideoPlayer
    )
    player._loop = loop
    player._frame_iterator = iter(frames)
    player._frame_delay = 42
    player._after_ids = set()
    player._stopped = False
    player.window = _Window()
    player._container = SimpleNamespace(close=lambda: None)
    return player


def test_end_of_stream_loops_by_restarting_and_scheduling(monkeypatch):
    player = _bare_player(loop=True)
    scheduled = []
    monkeypatch.setattr(player, "_restart_decoder", lambda: True)
    monkeypatch.setattr(player, "_schedule", lambda delay, callback: scheduled.append((delay, callback)))

    player._render_next_frame()

    assert scheduled == [(0, player._render_next_frame)]
    assert not player._stopped


def test_end_of_stream_closes_when_looping_is_disabled(monkeypatch):
    player = _bare_player(loop=False)
    closed = []
    monkeypatch.setattr(player, "close", lambda: closed.append(True))

    player._render_next_frame()

    assert closed == [True]


def test_close_cancels_every_callback_and_closes_container():
    closed = []
    player = _bare_player()
    player._after_ids = {"first", "second"}
    player._container = SimpleNamespace(close=lambda: closed.append(True))

    player.close()

    assert set(player.window.cancelled) == {"first", "second"}
    assert closed == [True]
    assert player._after_ids == set()
    assert player.window.destroyed


def test_monitor_selection_prefers_second_and_falls_back_to_primary(monkeypatch):
    player = _bare_player()
    monkeypatch.setattr(video_player, "_get_monitors", lambda: [(0, 0, 800, 600), (800, 0, 1920, 1080)])
    assert player._select_monitor() == video_player._MonitorBounds(800, 0, 1920, 1080)

    monkeypatch.setattr(video_player, "_get_monitors", lambda: [(-20, 10, 1024, 768)])
    assert player._select_monitor() == video_player._MonitorBounds(-20, 10, 1024, 768)


def test_missing_pyav_is_reported_before_window_creation(monkeypatch, tmp_path):
    media = tmp_path / "portrait.mp4"
    media.touch()
    monkeypatch.setattr(video_player, "av", None)

    try:
        video_player.play_video_on_second_screen(str(media))
    except RuntimeError as exc:
        assert "PyAV is not installed" in str(exc)
    else:  # pragma: no cover - assertion aid
        raise AssertionError("missing PyAV must produce a user-actionable error")

