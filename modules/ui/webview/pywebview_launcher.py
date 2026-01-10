"""Standalone entrypoint for opening a pywebview window."""

from __future__ import annotations

import argparse
import importlib.util
import sys

import webview


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Launch a pywebview browser window")
    parser.add_argument("url", help="URL to open")
    parser.add_argument("--title", default="Image Browser", help="Window title")
    parser.add_argument("--width", type=int, default=1100, help="Window width")
    parser.add_argument("--height", type=int, default=760, help="Window height")
    parser.add_argument("--min-width", type=int, default=900, help="Minimum window width")
    parser.add_argument("--min-height", type=int, default=620, help="Minimum window height")
    return parser.parse_args()


def _module_available(module_name: str) -> bool:
    return importlib.util.find_spec(module_name) is not None


def _qt_available() -> bool:
    return any(
        _module_available(module_name)
        for module_name in ("PyQt6", "PySide6", "PyQt5", "PySide2")
    )


def _cef_available() -> bool:
    return _module_available("cefpython3")


def _edgechromium_available() -> bool:
    return _module_available("clr")


def _webkit_available() -> bool:
    return _module_available("objc") or _module_available("AppKit")


def select_gui() -> str | None:
    if sys.platform.startswith("win"):
        preferred_guis = [("edgechromium", _edgechromium_available)]
    elif sys.platform == "darwin":
        preferred_guis = [("webkit", _webkit_available)]
    else:
        preferred_guis = [
            ("cef", _cef_available),
            ("qt", _qt_available),
        ]

    for gui_name, available in preferred_guis:
        if available():
            return gui_name

    modern_backends = (
        _edgechromium_available(),
        _webkit_available(),
        _cef_available(),
        _qt_available(),
    )
    if any(modern_backends):
        return None

    # TK is a safe fallback but has limited clipboard and context menu support.
    return "tk"


def main() -> None:
    args = parse_args()
    webview.create_window(
        args.title,
        args.url,
        width=args.width,
        height=args.height,
        min_size=(args.min_width, args.min_height),
        resizable=True,
    )
    webview.start(gui=select_gui())


if __name__ == "__main__":
    main()
