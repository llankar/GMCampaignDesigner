"""Models for campaign poster exports."""
from __future__ import annotations

from dataclasses import dataclass


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
