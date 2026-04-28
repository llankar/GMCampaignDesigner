"""Interaction helpers for audio bar filters."""

from __future__ import annotations

from typing import Any

from modules.audio.ui.filter_selection_resolver import resolve_category_mood_selection


def resolve_audio_filters(
    *,
    library: Any,
    section: str,
    category: str,
    preferred_mood: str | None,
) -> tuple[str, str | None, list[str]]:
    """Resolve and normalize category/mood selection for playlist updates."""
    mood = preferred_mood if preferred_mood not in {"", "No mood"} else None
    return resolve_category_mood_selection(
        library=library,
        section=section,
        category=category,
        preferred_mood=mood,
    )
