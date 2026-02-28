"""Rank-dependent limits for character creation progression."""

from __future__ import annotations


def max_favorite_skills(advancements: int) -> int:
    """Return the maximum number of favorite skills allowed for the current advancement count."""

    bonus_favorites = 0
    if advancements >= 3:
        bonus_favorites += 1
    if advancements >= 11:
        bonus_favorites += 1
    return 6 + bonus_favorites


def skill_cap_points_for_advancements(advancements: int) -> int:
    """Return max skill points by advancement thresholds."""

    if advancements <= 2:
        return 5
    if advancements <= 4:
        return 6
    if advancements <= 7:
        return 7
    if advancements <= 10:
        return 8
    return 9


def bonus_skill_points_from_advancements(advancement_choices: list[dict]) -> int:
    """Each skill-improvement advancement grants +1 spendable bonus-skill point."""

    return sum(1 for choice in advancement_choices if (choice or {}).get("type", "").strip() == "skill_improvement")
