"""Shortcut behavior tests for MainWindow handlers."""

import main_window


class _DummyMainWindow:
    def __init__(self) -> None:
        self.opened = False

    def open_image_library_browser(self):
        self.opened = True


def test_ctrl_i_opens_image_library() -> None:
    """Ctrl+I handler opens the shared image library and stops propagation."""
    app = _DummyMainWindow()
    bound_method = main_window.MainWindow._on_ctrl_i.__get__(app, _DummyMainWindow)

    result = bound_method()

    assert app.opened is True
    assert result == "break"
