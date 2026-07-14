"""Helpers for building filesystem-safe filenames."""

from __future__ import annotations

import re

_WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}
_INVALID_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_COLLAPSED_UNDERSCORES = re.compile(r"_+")


def safe_filename_component(value: object, fallback: str = "file") -> str:
    """Return a string safe to use as one segment of a filename on Windows/Linux."""
    text = str(value or "").strip()
    text = _INVALID_FILENAME_CHARS.sub("_", text)
    text = "".join(ch if ch.isalnum() or ch in {"_", "-", ".", " "} else "_" for ch in text)
    text = text.replace(" ", "_")
    text = _COLLAPSED_UNDERSCORES.sub("_", text).strip("._")
    if not text:
        text = fallback
    if text.upper() in _WINDOWS_RESERVED_NAMES:
        text = f"{text}_"
    return text
