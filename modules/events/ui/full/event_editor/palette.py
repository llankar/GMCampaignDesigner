from __future__ import annotations

from dataclasses import dataclass

from modules.helpers import theme_manager


@dataclass(frozen=True)
class EventEditorPalette:
    window_bg: str
    panel_bg: str
    panel_alt_bg: str
    hero_start: str
    hero_end: str
    border: str
    text_primary: str
    text_secondary: str
    accent: str
    accent_hover: str
    muted_chip: str
    input_bg: str
    input_border: str
    success: str
    warning: str


_BASE_PALETTE = EventEditorPalette(
    window_bg="#0f1724",
    panel_bg="#152033",
    panel_alt_bg="#1b2940",
    hero_start="#13243a",
    hero_end="#1d3558",
    border="#30415e",
    text_primary="#f5f8ff",
    text_secondary="#9fb2cd",
    accent="#4A8DFF",
    accent_hover="#3578eb",
    muted_chip="#223149",
    input_bg="#1b2740",
    input_border="#334766",
    success="#22c55e",
    warning="#f59e0b",
)

_THEME_OVERRIDES = {
    theme_manager.THEME_DEFAULT: {},
    theme_manager.THEME_MEDIEVAL: {
        "window_bg": "#17120f",
        "panel_bg": "#241a14",
        "panel_alt_bg": "#2d2218",
        "hero_start": "#2d2016",
        "hero_end": "#513822",
        "border": "#5f4735",
        "text_primary": "#f7ead8",
        "text_secondary": "#d0b491",
        "muted_chip": "#3b2a1c",
        "input_bg": "#312518",
        "input_border": "#735640",
        "warning": "#d19b49",
    },
    theme_manager.THEME_SF: {
        "window_bg": "#0c1611",
        "panel_bg": "#112019",
        "panel_alt_bg": "#142820",
        "hero_start": "#0f2419",
        "hero_end": "#13402c",
        "border": "#255641",
        "text_primary": "#e6fff1",
        "text_secondary": "#98cdb0",
        "muted_chip": "#143023",
        "input_bg": "#173126",
        "input_border": "#2a6f51",
        "warning": "#e7b64b",
    },
}


class _EventEditorPaletteProxy:
    def __getattr__(self, item: str):
        return getattr(get_event_editor_palette(), item)


EVENT_EDITOR_PALETTE = _EventEditorPaletteProxy()


def get_event_editor_palette(theme: str | None = None) -> EventEditorPalette:
    key = (theme or theme_manager.get_theme()).strip().lower()
    palette_values = dict(_BASE_PALETTE.__dict__)
    palette_values.update(_THEME_OVERRIDES.get(key, _THEME_OVERRIDES[theme_manager.THEME_DEFAULT]))

    tokens = theme_manager.get_tokens(key)
    palette_values["accent"] = tokens.get("button_fg", palette_values["accent"])
    palette_values["accent_hover"] = tokens.get("button_hover", palette_values["accent_hover"])
    palette_values["border"] = tokens.get("button_border", palette_values["border"])

    return EventEditorPalette(**palette_values)
