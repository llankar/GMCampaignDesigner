"""Standalone entrypoint for opening a pywebview window."""

from __future__ import annotations

import argparse

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
    webview.start(gui="tk")


if __name__ == "__main__":
    main()
