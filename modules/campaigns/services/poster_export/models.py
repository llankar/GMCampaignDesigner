"""Models and theme composition helpers for campaign poster exports."""
from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(frozen=True, slots=True)
class PosterTheme:
    """Color tokens used by the campaign poster renderer."""

    background: str
    surface: str
    elevated: str
    border: str
    text_primary: str
    text_secondary: str
    accent: str
    connector: str


DEFAULT_POSTER_THEME = PosterTheme(
    background="#0f172a",
    surface="#172033",
    elevated="#1f2a40",
    border="#334155",
    text_primary="#e2e8f0",
    text_secondary="#94a3b8",
    accent="#60a5fa",
    connector="#475569",
)


_HEX_COLOR_PATTERN = re.compile(r"^#[0-9a-fA-F]{6}$")
_MIN_PRIMARY_TEXT_CONTRAST = 4.5
_MIN_BORDER_CONTRAST = 1.5

_POSTER_TOKEN_MAP = {
    "background": "panel_bg",
    "surface": "panel_alt_bg",
    "elevated": "accent_button_fg",
    "accent": "button_fg",
    "connector": "button_border",
}


def build_poster_theme_from_tokens(tokens: dict[str, str] | None, *, min_text_contrast: float = _MIN_PRIMARY_TEXT_CONTRAST) -> PosterTheme:
    """Build a poster theme from UI tokens and auto-correct low-contrast values."""
    token_values = tokens or {}

    assigned = {
        field_name: _sanitize_hex(token_values.get(token_key), getattr(DEFAULT_POSTER_THEME, field_name))
        for field_name, token_key in _POSTER_TOKEN_MAP.items()
    }

    theme = PosterTheme(
        background=assigned["background"],
        surface=assigned["surface"],
        elevated=assigned["elevated"],
        border=DEFAULT_POSTER_THEME.border,
        text_primary=DEFAULT_POSTER_THEME.text_primary,
        text_secondary=DEFAULT_POSTER_THEME.text_secondary,
        accent=assigned["accent"],
        connector=assigned["connector"],
    )

    return _ensure_theme_contrast(theme, min_text_contrast=min_text_contrast)


def _ensure_theme_contrast(theme: PosterTheme, *, min_text_contrast: float) -> PosterTheme:
    """Force safe fallback colors when theme contrast is below minimum thresholds."""
    text_primary = _pick_readable_color(
        background=theme.surface,
        preferred=theme.text_primary,
        min_ratio=min_text_contrast,
        fallback_dark="#0b1220",
        fallback_light="#f8fafc",
    )
    text_secondary = _pick_readable_color(
        background=theme.surface,
        preferred=theme.text_secondary,
        min_ratio=max(3.0, min_text_contrast - 1.5),
        fallback_dark="#1e293b",
        fallback_light="#cbd5e1",
    )
    border = _pick_readable_color(
        background=theme.surface,
        preferred=theme.border,
        min_ratio=_MIN_BORDER_CONTRAST,
        fallback_dark="#334155",
        fallback_light="#94a3b8",
    )
    accent = _pick_readable_color(
        background=theme.surface,
        preferred=theme.accent,
        min_ratio=3.0,
        fallback_dark="#1d4ed8",
        fallback_light="#93c5fd",
    )
    connector = _pick_readable_color(
        background=theme.background,
        preferred=theme.connector,
        min_ratio=1.4,
        fallback_dark="#334155",
        fallback_light="#94a3b8",
    )

    return PosterTheme(
        background=theme.background,
        surface=theme.surface,
        elevated=theme.elevated,
        border=border,
        text_primary=text_primary,
        text_secondary=text_secondary,
        accent=accent,
        connector=connector,
    )


def contrast_ratio(first_hex: str, second_hex: str) -> float:
    """Compute WCAG contrast ratio for two #RRGGBB colors."""
    first = _hex_to_rgb(first_hex)
    second = _hex_to_rgb(second_hex)
    first_luminance = _relative_luminance(first)
    second_luminance = _relative_luminance(second)
    lighter = max(first_luminance, second_luminance)
    darker = min(first_luminance, second_luminance)
    return (lighter + 0.05) / (darker + 0.05)


def _pick_readable_color(background: str, preferred: str, *, min_ratio: float, fallback_dark: str, fallback_light: str) -> str:
    if contrast_ratio(background, preferred) >= min_ratio:
        return preferred

    dark_ratio = contrast_ratio(background, fallback_dark)
    light_ratio = contrast_ratio(background, fallback_light)

    if dark_ratio >= min_ratio and dark_ratio >= light_ratio:
        return fallback_dark
    if light_ratio >= min_ratio:
        return fallback_light
    return fallback_dark if dark_ratio >= light_ratio else fallback_light


def _sanitize_hex(color: str | None, fallback: str) -> str:
    if isinstance(color, str) and _HEX_COLOR_PATTERN.match(color.strip()):
        return color.strip().lower()
    return fallback


def _hex_to_rgb(color: str) -> tuple[int, int, int]:
    sanitized = _sanitize_hex(color, "#000000")
    return int(sanitized[1:3], 16), int(sanitized[3:5], 16), int(sanitized[5:7], 16)


def _relative_luminance(rgb: tuple[int, int, int]) -> float:
    channels = []
    for value in rgb:
        channel = value / 255.0
        if channel <= 0.03928:
            channels.append(channel / 12.92)
        else:
            channels.append(((channel + 0.055) / 1.055) ** 2.4)
    red, green, blue = channels
    return (0.2126 * red) + (0.7152 * green) + (0.0722 * blue)
