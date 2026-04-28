"""Shared visual styles for compact floating bars (dice/audio)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CompactBarStyle:
    """Palette and sizing tokens for compact bars."""

    shell_bg: str
    content_bg: str
    panel_border: str
    accent_soft: str
    accent_strong: str
    accent_hover: str
    badge_fg: str
    badge_text: str
    button_text: str
    pill_radius: int = 12
    button_radius: int = 10
    border_width: int = 1


def build_compact_bar_style(tokens: dict) -> CompactBarStyle:
    """Build a vivid style from the current theme tokens."""
    accent = tokens.get("button_fg") or "#11a054"
    accent_hover = tokens.get("button_hover") or "#0d7b40"
    badge_text = tokens.get("sidebar_active_fg") or "#ecfff5"
    return CompactBarStyle(
        shell_bg=tokens.get("panel_bg") or "#0f1a12",
        content_bg=tokens.get("panel_alt_bg") or "#13261a",
        panel_border="#2ecf8b",
        accent_soft="#1a6f47",
        accent_strong=accent,
        accent_hover=accent_hover,
        badge_fg="#0f5133",
        badge_text=badge_text,
        button_text="#ecfff5",
    )
