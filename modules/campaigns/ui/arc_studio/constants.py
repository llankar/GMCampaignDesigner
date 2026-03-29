from __future__ import annotations

from modules.generic.editor.styles import EDITOR_PALETTE

STATUS_COLORS = {
    "planned": "#6B7280",
    "in progress": "#2563EB",
    "running": "#2563EB",
    "active": "#2563EB",
    "blocked": "#D97706",
    "resolved": "#059669",
    "completed": "#059669",
}


def color_for_status(status: str) -> str:
    return STATUS_COLORS.get((status or "").strip().casefold(), EDITOR_PALETTE["accent"])
