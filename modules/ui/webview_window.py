"""Helpers for launching a pywebview window."""

from __future__ import annotations

import threading

import webview

from modules.helpers.logging_helper import log_exception, log_module_import

log_module_import(__name__)

_window: webview.Window | None = None
_thread: threading.Thread | None = None
_lock = threading.Lock()


def _run_webview(title: str, url: str) -> None:
    global _window
    try:
        _window = webview.create_window(title, url)
        webview.start(gui="tkinter", debug=False)
    except Exception as exc:  # pragma: no cover - UI fallback
        log_exception(
            f"Unable to launch webview for {url}: {exc}",
            func_name="webview_window._run_webview",
        )
    finally:
        _window = None


def open_browser_window(title: str, url: str) -> None:
    """Open or focus the webview browser window at the given URL."""
    global _thread
    with _lock:
        if _window is not None:
            _window.load_url(url)
            _window.show()
            return
        if _thread is None or not _thread.is_alive():
            _thread = threading.Thread(
                target=_run_webview,
                args=(title, url),
                daemon=True,
            )
            _thread.start()
