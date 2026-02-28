"""Rank-dependent limits for character creation progression."""

from __future__ import annotations


def max_favorite_skills(advancements: int) -> int:
    """Return the maximum number of favorite skills allowed for the current advancement count."""

    bonus_favorites = 0
    if advancements >= 7:
        bonus_favorites += 1
    if advancements >= 40:
        bonus_favorites += 1
    return 6 + bonus_favorites


def skill_cap_points_for_advancements(advancements: int) -> int:
    """Return max skill points by advancement thresholds."""
    max = 9
    if advancements <= 7:
        max = 5
    if advancements <= 15:
        max= 6
    if advancements <= 27:
        max= 7
    if advancements <= 39:
        max= 8
    return max


def bonus_skill_points_from_advancements(advancement_choices: list[dict]) -> int:
    """Each skill-improvement advancement grants +1 spendable bonus-skill point."""

    return sum(1 for choice in advancement_choices if (choice or {}).get("type", "").strip() == "skill_improvement")
