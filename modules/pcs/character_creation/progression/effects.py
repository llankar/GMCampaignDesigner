"""Apply advancement choices to computed character sheet values."""

from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata

from ..constants import SKILLS


@dataclass
class AdvancementEffects:
    effective_skill_points: dict[str, int]
    superficial_health_bonus: int
    extra_assets: list[str]


def _extract_matching_skills(raw_details: str) -> list[str]:
    if not raw_details:
        return []

    def normalize_token(token: str) -> str:
        lowered = token.strip().lower()
        normalized = unicodedata.normalize("NFKD", lowered)
        return "".join(char for char in normalized if not unicodedata.combining(char))

    normalized_lookup = {normalize_token(skill): skill for skill in SKILLS}
    tokens = re.split(r"(?:\s*(?:,|;|/|\||\+)\s*|\set\s)", raw_details, flags=re.IGNORECASE)

    resolved: list[str] = []
    for token in tokens:
        skill = normalized_lookup.get(normalize_token(token))
        if skill:
            resolved.append(skill)
    return resolved


def apply_advancement_effects(
    base_skill_points: dict[str, int],
    favorites: list[str],
    advancement_choices: list[dict],
    is_superhero: bool,
) -> AdvancementEffects:
    effective_skill_points = dict(base_skill_points)
    superficial_health_bonus = 0
    extra_assets: list[str] = []
    favorite_set = set(favorites)

    for choice in advancement_choices:
        choice_type = (choice or {}).get("type", "").strip()
        details = (choice or {}).get("details", "").strip()

        if choice_type == "new_edge":
            if details:
                extra_assets.append(f"Atout: {details}")
            else:
                extra_assets.append("Atout supplémentaire")

        elif choice_type == "superficial_health":
            superficial_health_bonus += 10 if is_superhero else 5

        elif choice_type == "new_skill":
            for skill in _extract_matching_skills(details):
                effective_skill_points[skill] = max(effective_skill_points.get(skill, 0), 1)

        elif choice_type == "skill_improvement":
            selected_skills = _extract_matching_skills(details)
            if not selected_skills:
                continue

            selected_favorites = [skill for skill in selected_skills if skill in favorite_set]
            if len(selected_favorites) >= 2:
                for skill in selected_favorites[:2]:
                    effective_skill_points[skill] = effective_skill_points.get(skill, 0) + 1
                continue

            for skill in selected_skills:
                effective_skill_points[skill] = effective_skill_points.get(skill, 0) + 1
                break

    return AdvancementEffects(
        effective_skill_points=effective_skill_points,
        superficial_health_bonus=superficial_health_bonus,
        extra_assets=extra_assets,
    )
