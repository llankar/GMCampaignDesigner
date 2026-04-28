"""Shared widgets for session dock UI elements."""

from .icon_button import DockIconButton
from .segmented_controls import DockSegmentedControl
from .status_pill import StatusPill
from .tooltip_helpers import attach_tooltip

__all__ = [
    "DockIconButton",
    "DockSegmentedControl",
    "StatusPill",
    "attach_tooltip",
]
