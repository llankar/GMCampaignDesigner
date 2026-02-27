"""Helpers for character-creation point accounting."""

from __future__ import annotations


def summarize_point_budgets(
    base_points: dict[str, int],
    bonus_points: dict[str, int],
    favorites: list[str],
    *,
    total_base_points: int = 15,
) -> dict[str, int]:
    """Return point usage summary for UI display and validation hints."""

    normalized_base = {skill: max(0, int(value)) for skill, value in base_points.items()}
    normalized_bonus = {skill: max(0, int(value)) for skill, value in bonus_points.items()}
    favorite_set = {skill for skill in favorites if skill in normalized_base}

    spent_base = sum(normalized_base.values())
    generated_bonus = sum(normalized_base.get(skill, 0) for skill in favorite_set)
    used_bonus = sum(normalized_bonus.values())

    return {
        "spent_base": spent_base,
        "remaining_base": total_base_points - spent_base,
        "generated_bonus": generated_bonus,
        "used_bonus": used_bonus,
        "remaining_bonus": generated_bonus - used_bonus,
    }
