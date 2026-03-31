"""Resolution helpers for audio filter selection."""
from __future__ import annotations

from typing import Any


def resolve_category_mood_selection(
    library: Any,
    section: str,
    category: str,
    preferred_mood: str | None,
) -> tuple[str, str | None, list[str]]:
    """Resolve category mood selection."""
    categories = _safe_list_categories(library, section)
    if not categories:
        return "", None, []

    resolved_category = category if category in categories else categories[0]
    moods = _safe_list_moods(library, section, resolved_category)
    if preferred_mood and preferred_mood in moods:
        resolved_mood: str | None = preferred_mood
    else:
        resolved_mood = None
    return resolved_category, resolved_mood, moods


def _safe_list_categories(library: Any, section: str) -> list[str]:
    """Internal helper for safe list categories."""
    try:
        return list(library.get_categories(section))
    except Exception:
        return []


def _safe_list_moods(library: Any, section: str, category: str) -> list[str]:
    """Internal helper for safe list moods."""
    if not category:
        return []
    try:
        return list(library.get_moods(section, category))
    except Exception:
        return []
