"""Helpers for character-creation point accounting."""

from __future__ import annotations


def compute_favorite_bonus(base_points: dict[str, int], favorites: list[str]) -> dict[str, int]:
    """Distribute favorite-skill bonus points to *other* favorite skills.

    Each point invested in a favored skill grants one free point that is assigned to
    another favored skill (never the same source skill).
    """

    bonuses = {skill: 0 for skill in base_points}
    ordered_favorites = [skill for skill in favorites if skill in base_points]
    if len(ordered_favorites) < 2:
        return bonuses

    for source_index, source in enumerate(ordered_favorites):
        points_spent = max(0, int(base_points.get(source, 0)))
        for i in range(points_spent):
            target_index = (source_index + 1 + i) % len(ordered_favorites)
            target = ordered_favorites[target_index]
            if target == source:
                target_index = (target_index + 1) % len(ordered_favorites)
                target = ordered_favorites[target_index]
            bonuses[target] += 1
    return bonuses


def summarize_point_budgets(base_points: dict[str, int], favorites: list[str], *, total_base_points: int = 15) -> dict[str, int]:
    """Return current point usage summary for UI display."""

    spent_base = sum(max(0, int(value)) for value in base_points.values())
    favored_spent = sum(max(0, int(base_points.get(skill, 0))) for skill in favorites if skill in base_points)
    return {
        "spent_base": spent_base,
        "remaining_base": total_base_points - spent_base,
        "spent_favored": favored_spent,
        "free_favored_points": favored_spent,
    }
