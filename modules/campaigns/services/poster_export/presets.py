"""Curated reusable presets for poster themes."""
from __future__ import annotations

from .models import PosterTheme


DARK_POSTER_THEME = PosterTheme(
    background="#0b1020",
    surface="#121a2e",
    elevated="#1a2540",
    border="#2f3d62",
    text_primary="#e5edff",
    text_secondary="#a8b6db",
    accent="#6ea8ff",
    connector="#4a5c84",
)

NEON_POSTER_THEME = PosterTheme(
    background="#080914",
    surface="#10132a",
    elevated="#171b3b",
    border="#305f9c",
    text_primary="#eff8ff",
    text_secondary="#a3d7ff",
    accent="#39e6ff",
    connector="#4f72c6",
)
