from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AudioBarFilterOptions:
    categories: list[str]
    moods: list[str]
    category: str
    mood: str


def build_audio_bar_filter_options(
    *,
    library: Any,
    section: str,
    preferred_category: str = "",
    preferred_mood: str = "",
) -> AudioBarFilterOptions:
    categories = list(_safe_list_categories(library, section))
    category = _pick_value(categories, preferred_category)
    moods = list(_safe_list_moods(library, section, category)) if category else []
    mood = _pick_value(moods, preferred_mood)
    return AudioBarFilterOptions(
        categories=categories,
        moods=moods,
        category=category,
        mood=mood,
    )


def _safe_list_categories(library: Any, section: str) -> list[str]:
    try:
        return list(library.get_categories(section))
    except Exception:
        return []


def _safe_list_moods(library: Any, section: str, category: str) -> list[str]:
    if not category:
        return []
    try:
        return list(library.get_moods(section, category))
    except Exception:
        return []


def _pick_value(values: list[str], preferred: str) -> str:
    if preferred and preferred in values:
        return preferred
    if values:
        return values[0]
    return ""
