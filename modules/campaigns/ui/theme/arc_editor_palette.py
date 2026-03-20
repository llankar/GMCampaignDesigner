from __future__ import annotations

from dataclasses import dataclass

from modules.helpers import theme_manager


@dataclass(frozen=True)
class ArcEditorPalette:
    """Centralized colors used by the campaign arc editor."""

    window_bg: str
    surface: str
    surface_alt: str
    border: str
    text_primary: str
    text_secondary: str
    accent: str
    accent_soft: str
    success: str
    success_hover: str
    danger: str
    danger_hover: str
    chip_bg: str
    chip_border: str
    hero_gradient_start: str
    hero_gradient_end: str


_BASE_PALETTE = ArcEditorPalette(
    window_bg="#10151d",
    surface="#161d27",
    surface_alt="#1c2633",
    border="#2c3a4c",
    text_primary="#f3f7ff",
    text_secondary="#9eacc0",
    accent="#38bdf8",
    accent_soft="#15384a",
    success="#22c55e",
    success_hover="#16a34a",
    danger="#334155",
    danger_hover="#475569",
    chip_bg="#0f2533",
    chip_border="#21465f",
    hero_gradient_start="#102033",
    hero_gradient_end="#143a2b",
)

_THEME_OVERRIDES = {
    theme_manager.THEME_DEFAULT: {},
    theme_manager.THEME_MEDIEVAL: {
        "window_bg": "#17120f",
        "surface": "#211913",
        "surface_alt": "#2b2118",
        "border": "#5f4735",
        "text_primary": "#f7ead8",
        "text_secondary": "#ceb28e",
        "accent": "#8b5a2b",
        "accent_soft": "#3a2817",
        "success": "#9f6b2f",
        "success_hover": "#7f5321",
        "danger": "#544133",
        "danger_hover": "#6a5240",
        "chip_bg": "#2d2219",
        "chip_border": "#735640",
        "hero_gradient_start": "#2a1f16",
        "hero_gradient_end": "#4b3320",
    },
    theme_manager.THEME_SF: {
        "window_bg": "#0d1711",
        "surface": "#122019",
        "surface_alt": "#152720",
        "border": "#255641",
        "text_primary": "#e6fff1",
        "text_secondary": "#98cdb0",
        "accent": "#11a054",
        "accent_soft": "#113725",
        "success": "#11a054",
        "success_hover": "#0d7b40",
        "danger": "#1f4b35",
        "danger_hover": "#2b6548",
        "chip_bg": "#10261c",
        "chip_border": "#1b7a52",
        "hero_gradient_start": "#0f2419",
        "hero_gradient_end": "#13402c",
    },
}


class _ArcEditorPaletteProxy:
    """Resolve palette values from the currently active application theme."""

    def __getattr__(self, item: str):
        return getattr(get_arc_editor_palette(), item)


def get_arc_editor_palette(theme: str | None = None) -> ArcEditorPalette:
    """Return an arc-editor palette aligned with the active UI theme."""

    key = (theme or theme_manager.get_theme()).strip().lower()
    palette_values = dict(_BASE_PALETTE.__dict__)
    palette_values.update(_THEME_OVERRIDES.get(key, _THEME_OVERRIDES[theme_manager.THEME_DEFAULT]))

    tokens = theme_manager.get_tokens(key)
    palette_values["accent"] = tokens.get("button_fg", palette_values["accent"])
    palette_values["success"] = tokens.get("button_fg", palette_values["success"])
    palette_values["success_hover"] = tokens.get("button_hover", palette_values["success_hover"])
    palette_values["chip_border"] = tokens.get("button_border", palette_values["chip_border"])

    return ArcEditorPalette(**palette_values)


ARC_EDITOR_PALETTE = _ArcEditorPaletteProxy()
