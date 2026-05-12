"""Shortcut behavior tests for MainWindow handlers."""

import main_window


class _DummyMainWindow:
    def __init__(self) -> None:
        self.opened = False

    def open_image_library_browser(self):
        self.opened = True


class _HugeRun:
    def __str__(self) -> str:
        return "x" * 12_000


def test_ctrl_i_opens_image_library() -> None:
    """Ctrl+I handler opens the shared image library and stops propagation."""
    app = _DummyMainWindow()
    bound_method = main_window.MainWindow._on_ctrl_i.__get__(app, _DummyMainWindow)

    result = bound_method()

    assert app.opened is True
    assert result == "break"


def test_hierarchy_validation_callback_returns_none_to_tk(monkeypatch) -> None:
    """Tk commands must not receive the full validation run object."""
    from src.ui.validation.campaign_validation_launcher import (
        CampaignHierarchyValidationLauncher,
    )

    launched = []

    def fake_launch(self):
        launched.append(self.app)
        return _HugeRun()

    monkeypatch.setattr(CampaignHierarchyValidationLauncher, "launch", fake_launch)
    app = _DummyMainWindow()
    bound_method = main_window.MainWindow.open_hierarchy_validation.__get__(
        app,
        _DummyMainWindow,
    )

    result = bound_method()

    assert launched == [app]
    assert result is None
