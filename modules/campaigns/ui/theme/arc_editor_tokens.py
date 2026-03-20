from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ArcEditorPalette:
    """Centralized colors and copy tokens for the campaign arc editor."""

    window_bg: str = "#10151d"
    surface: str = "#161d27"
    surface_alt: str = "#1c2633"
    border: str = "#2c3a4c"
    text_primary: str = "#f3f7ff"
    text_secondary: str = "#9eacc0"
    accent: str = "#38bdf8"
    accent_soft: str = "#15384a"
    success: str = "#22c55e"
    success_hover: str = "#16a34a"
    danger: str = "#334155"
    danger_hover: str = "#475569"
    chip_bg: str = "#0f2533"
    chip_border: str = "#21465f"
    hero_gradient_start: str = "#102033"
    hero_gradient_end: str = "#143a2b"


ARC_EDITOR_PALETTE = ArcEditorPalette()

ARC_EDITOR_STATUS_HINTS = {
    "Planned": "Outline the core conflict and pin the first missions players should hear about.",
    "In Progress": "Keep objectives concrete so you can track progress between linked scenarios.",
    "Paused": "Capture why the arc cooled off and what would reignite it later in the campaign.",
    "Completed": "Record the payoff and legacy so future arcs can build on the fallout.",
}
