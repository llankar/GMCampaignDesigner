"""Window chrome helpers for detached GM Table workspaces."""

from __future__ import annotations

from typing import Any


def remove_native_window_decorations(window: Any) -> None:
    """Hide the operating-system title bar around a detached GM Table window."""
    window.overrideredirect(True)
