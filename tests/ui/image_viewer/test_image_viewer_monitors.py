"""Tests for monitor detection and single-monitor overlay behavior."""

from modules.ui import image_viewer


class _FakeWindow:
    def __init__(self):
        self.calls = []

    def lift(self):
        self.calls.append(("lift",))

    def focus_force(self):
        self.calls.append(("focus_force",))

    def attributes(self, *args):
        self.calls.append(("attributes",) + args)


def test_configure_single_monitor_overlay_brings_window_to_front():
    win = _FakeWindow()

    image_viewer._configure_single_monitor_overlay(win, [(0, 0, 1920, 1080)])

    assert ("lift",) in win.calls
    assert ("focus_force",) in win.calls
    assert ("attributes", "-topmost", True) in win.calls


def test_get_monitors_uses_fallback_when_not_windows(monkeypatch):
    expected = [(0, 0, 1280, 720)]
    monkeypatch.setattr(image_viewer.os, "name", "posix")
    monkeypatch.setattr(image_viewer, "_fallback_primary_monitor", lambda: expected)

    monitors = image_viewer._get_monitors()

    assert monitors == expected


def test_get_monitors_uses_fallback_when_windows_enum_fails(monkeypatch):
    expected = [(0, 0, 1366, 768)]

    monkeypatch.setattr(image_viewer.os, "name", "nt")
    monkeypatch.setattr(image_viewer, "_fallback_primary_monitor", lambda: expected)
    monkeypatch.setattr(
        image_viewer.ctypes,
        "WINFUNCTYPE",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("boom")),
        raising=False,
    )

    monitors = image_viewer._get_monitors()

    assert monitors == expected
