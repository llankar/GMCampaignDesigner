"""Theme helpers for dashboard."""

from __future__ import annotations

from dataclasses import dataclass

from modules.helpers import theme_manager


@dataclass(frozen=True)
class DashboardTheme:
    panel_bg: str = "#111827"
    panel_alt_bg: str = "#1f2937"
    card_bg: str = "#172033"
    card_border: str = "#2a3854"
    text_primary: str = "#e5ecff"
    text_secondary: str = "#9fb0d9"
    accent: str = "#7c3aed"
    accent_hover: str = "#6d28d9"
    accent_soft: str = "#a78bfa"
    button_fg: str = "#25314a"
    button_hover: str = "#334567"
    input_bg: str = "#1d3352"
    input_button: str = "#2b4a75"
    input_hover: str = "#3a6294"
    arc_track: str = "#2f3d5c"
    arc_complete: str = "#22c55e"
    arc_active: str = "#f59e0b"
    arc_planned: str = "#60a5fa"


def get_dashboard_theme() -> DashboardTheme:
    """Return dashboard theme."""
    key = theme_manager.get_theme()
    tokens = theme_manager.get_tokens(key)

    if key == theme_manager.THEME_MEDIEVAL:
        return DashboardTheme(
            panel_bg=tokens.get("panel_bg", "#2e241a"),
            panel_alt_bg=tokens.get("panel_alt_bg", "#362a1e"),
            card_bg="#3d2d20",
            card_border="#6f5033",
            text_primary="#f3e7d1",
            text_secondary="#d7be95",
            accent=tokens.get("button_fg", "#8b5a2b"),
            accent_hover=tokens.get("button_hover", "#6e4521"),
            accent_soft="#b27d42",
            button_fg="#5c3f25",
            button_hover="#6f5033",
            input_bg="#4a331f",
            input_button="#6f5033",
            input_hover="#8a623d",
            arc_track="#5c4733",
            arc_complete="#7ecb70",
            arc_active="#d39a4a",
            arc_planned="#bf8a5b",
        )

    if key == theme_manager.THEME_SF:
        return DashboardTheme(
            panel_bg=tokens.get("panel_bg", "#0f1a12"),
            panel_alt_bg=tokens.get("panel_alt_bg", "#13261a"),
            card_bg="#143122",
            card_border="#1f573c",
            text_primary="#d8ffe8",
            text_secondary="#95d8b5",
            accent=tokens.get("button_fg", "#11a054"),
            accent_hover=tokens.get("button_hover", "#0d7b40"),
            accent_soft="#45d58f",
            button_fg="#1a4d35",
            button_hover="#226646",
            input_bg="#17452f",
            input_button="#1f573c",
            input_hover="#27734f",
            arc_track="#245740",
            arc_complete="#8af7b5",
            arc_active="#f2d36b",
            arc_planned="#58c0a3",
        )

    return DashboardTheme(
        panel_bg=tokens.get("panel_bg", "#111c2a"),
        panel_alt_bg=tokens.get("panel_alt_bg", "#132133"),
        accent=tokens.get("button_fg", "#0077CC"),
        accent_hover=tokens.get("button_hover", "#005fa3"),
        accent_soft="#67b6ff",
        button_fg="#25314a",
        button_hover="#334567",
        input_bg="#1d3352",
        input_button="#2b4a75",
        input_hover="#3a6294",
    )


class _LiveDashboardTheme:
    """Resolve dashboard colors lazily so runtime theme changes are reflected."""

    def __getattr__(self, item: str):
        """Handle getattr."""
        return getattr(get_dashboard_theme(), item)


DASHBOARD_THEME = _LiveDashboardTheme()
