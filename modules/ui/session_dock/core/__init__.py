"""Core session dock primitives (state, window, shortcuts)."""

from .dock_shortcuts import DockShortcutManager
from .dock_state import DockState, DockStateStore
from .dock_window import DockWindow

__all__ = ["DockShortcutManager", "DockState", "DockStateStore", "DockWindow"]
