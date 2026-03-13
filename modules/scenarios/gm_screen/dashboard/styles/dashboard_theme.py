from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DashboardTheme:
    panel_bg: str = "#111827"
    panel_alt_bg: str = "#1f2937"
    card_bg: str = "#172033"
    card_border: str = "#2a3854"
    text_primary: str = "#e5ecff"
    text_secondary: str = "#9fb0d9"
    accent: str = "#7c3aed"
    accent_soft: str = "#a78bfa"
    arc_track: str = "#2f3d5c"
    arc_complete: str = "#22c55e"
    arc_active: str = "#f59e0b"
    arc_planned: str = "#60a5fa"


DASHBOARD_THEME = DashboardTheme()
