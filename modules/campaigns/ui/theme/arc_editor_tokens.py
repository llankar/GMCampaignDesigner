from __future__ import annotations

from .arc_editor_palette import ARC_EDITOR_PALETTE, ArcEditorPalette, get_arc_editor_palette

ARC_EDITOR_STATUS_HINTS = {
    "Planned": "Outline the core conflict and pin the first missions players should hear about.",
    "In Progress": "Keep objectives concrete so you can track progress between linked scenarios.",
    "Paused": "Capture why the arc cooled off and what would reignite it later in the campaign.",
    "Completed": "Record the payoff and legacy so future arcs can build on the fallout.",
}

__all__ = [
    "ARC_EDITOR_PALETTE",
    "ARC_EDITOR_STATUS_HINTS",
    "ArcEditorPalette",
    "get_arc_editor_palette",
]
