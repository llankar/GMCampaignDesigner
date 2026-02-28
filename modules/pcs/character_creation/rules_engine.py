"""Rules engine for Savage Fate character creation."""

from __future__ import annotations

from dataclasses import dataclass

from .constants import DIE_STEPS, RANK_TABLE, SKILLS
from .points import summarize_point_budgets
from .progression.rank_limits import (
    bonus_skill_points_from_advancements,
    max_favorite_skills,
    skill_cap_points_for_advancements,
)
from .progression import BASE_FEAT_COUNT, apply_advancement_effects, prowess_points_from_advancement_choices


class CharacterCreationError(ValueError):
    """Raised when character creation payload violates Savage Fate rules."""


@dataclass
class CharacterCreationResult:
    rank_name: str
    rank_index: int
    skill_dice: dict[str, str]
    effective_skill_points: dict[str, int]
    superficial_health: int
    extra_assets: list[str]


LIMITED_ADVANCEMENT_TYPES = {
    "new_edge",
    "superficial_health",
    "prowess_points",
}


def _validate_advancement_choices(advancements: int, choices: list[dict]) -> None:
    if advancements <= 0:
        return

    if len(choices) != advancements:
        raise CharacterCreationError(
            f"Le nombre de choix d'avancement ({len(choices)}) doit être égal au total d'avancements ({advancements})."
        )

    per_rank_usage: dict[str, set[str]] = {}
    for index, choice in enumerate(choices, start=1):
        choice_type = (choice or {}).get("type", "").strip()
        if not choice_type:
            raise CharacterCreationError(f"L'avancement #{index} n'a pas de type sélectionné.")

        rank_name, _, _ = rank_from_advancements(index)
        if choice_type in LIMITED_ADVANCEMENT_TYPES:
            used = per_rank_usage.setdefault(rank_name, set())
            if choice_type in used:
                raise CharacterCreationError(
                    f"L'option '{choice_type}' ne peut être choisie qu'une seule fois au rang '{rank_name}'."
                )
            used.add(choice_type)


def rank_from_advancements(advancements: int) -> tuple[str, int, int]:
    for idx, (start, end, rank_name, skill_cap_points) in enumerate(RANK_TABLE):
        if start <= advancements <= end:
            return rank_name, idx, skill_cap_points
    if advancements < 0:
        raise CharacterCreationError("Le nombre d'avancements ne peut pas être négatif.")
    return RANK_TABLE[-1][2], len(RANK_TABLE) - 1, RANK_TABLE[-1][3]



def build_character(character_input: dict) -> CharacterCreationResult:
    name = (character_input.get("name") or "").strip()
    concept = (character_input.get("concept") or "").strip()
    flaw = (character_input.get("flaw") or "").strip()
    if not name:
        raise CharacterCreationError("Le nom est obligatoire.")
    if not concept or not flaw:
        raise CharacterCreationError("Concept et défaut sont obligatoires.")

    advancements = int(character_input.get("advancements", 0))
    favorite_limit = max_favorite_skills(advancements)

    favorites = character_input.get("favorites") or []
    if len(favorites) < 6:
        raise CharacterCreationError("Il faut au minimum 6 compétences favorites.")
    if len(favorites) > favorite_limit:
        raise CharacterCreationError(
            f"Le maximum de compétences favorites pour ce rang est {favorite_limit}."
        )
    if len(set(favorites)) != len(favorites):
        raise CharacterCreationError("Les compétences favorites doivent être uniques.")
    for skill in favorites:
        if skill not in SKILLS:
            raise CharacterCreationError(f"Compétence favorite invalide: {skill}")

    base_points = {skill: int((character_input.get("skills") or {}).get(skill, 0)) for skill in SKILLS}
    bonus_points = {skill: int((character_input.get("bonus_skills") or {}).get(skill, 0)) for skill in SKILLS}

    total_points = sum(base_points.values())
    if total_points != 15:
        raise CharacterCreationError(f"La somme des points de compétence de base doit être 15 (actuel: {total_points}).")
    for skill, points in base_points.items():
        if points < 0 or points > 5:
            raise CharacterCreationError(f"La compétence '{skill}' doit être entre 0 et 5 à la création.")

    for skill, bonus in bonus_points.items():
        if bonus < 0:
            raise CharacterCreationError(f"Le bonus de compétence '{skill}' ne peut pas être négatif.")
        if bonus > 0 and skill not in favorites:
            raise CharacterCreationError(f"Les points bonus ne peuvent être investis que dans les compétences favorites ({skill}).")

    advancement_choices = character_input.get("advancement_choices") or []
    bonus_from_advancements = bonus_skill_points_from_advancements(advancement_choices)

    summary = summarize_point_budgets(
        base_points,
        bonus_points,
        favorites,
        extra_generated_bonus=bonus_from_advancements,
    )
    if summary["used_bonus"] > summary["generated_bonus"]:
        raise CharacterCreationError(
            f"Points bonus insuffisants: {summary['used_bonus']} utilisés pour {summary['generated_bonus']} générés."
        )

    _validate_advancement_choices(advancements, advancement_choices)
    rank_name, rank_index, _ = rank_from_advancements(advancements)
    skill_cap_points = skill_cap_points_for_advancements(advancements)

    effective_points = {skill: base_points[skill] + bonus_points.get(skill, 0) for skill in SKILLS}
    progression_effects = apply_advancement_effects(
        base_skill_points=effective_points,
        favorites=favorites,
        advancement_choices=advancement_choices,
        is_superhero=bool(character_input.get("is_superhero")),
    )
    effective_points = progression_effects.effective_skill_points

    for skill, pts in effective_points.items():
        if pts > skill_cap_points:
            raise CharacterCreationError(
                f"{skill} dépasse le cap du rang ({DIE_STEPS.get(skill_cap_points, 'd12+4')})."
            )

    feats = character_input.get("feats") or []
    prowess_budgets = prowess_points_from_advancement_choices(advancement_choices)
    expected_feat_total = BASE_FEAT_COUNT + len(prowess_budgets)
    if len(feats) != expected_feat_total:
        raise CharacterCreationError(
            f"Le nombre de prouesses doit être {expected_feat_total} (base {BASE_FEAT_COUNT} + {len(prowess_budgets)} via avancements)."
        )
    for feat_index, feat in enumerate(feats):
        options = feat.get("options") or []
        limitation = (feat.get("limitation") or "").strip()
        if len(options) != 3:
            raise CharacterCreationError("Chaque prouesse doit contenir exactement 3 options.")
        if not limitation:
            raise CharacterCreationError("Chaque prouesse doit définir une limitation.")

        expected_points = 0 if feat_index < BASE_FEAT_COUNT else prowess_budgets[feat_index - BASE_FEAT_COUNT]
        actual_points = int(feat.get("prowess_points", expected_points) or 0)
        if actual_points != expected_points:
            raise CharacterCreationError(
                f"La prouesse #{feat_index + 1} doit avoir {expected_points} point(s) de prouesse."
            )

    equipment = character_input.get("equipment") or {}
    for key in ("weapon", "armor", "utility"):
        if key not in equipment:
            raise CharacterCreationError("L'équipement doit contenir arme, armure et utilitaire.")
    pe_alloc = {k: int(v) for k, v in (character_input.get("equipment_pe") or {}).items()}
    if sum(pe_alloc.get(k, 0) for k in ("weapon", "armor", "utility")) != 3:
        raise CharacterCreationError("Les PE de départ doivent totaliser 3 (1/1/1).")

    superficial_health = (10 if character_input.get("is_superhero") else 5) + 5 + rank_index + progression_effects.superficial_health_bonus

    skill_dice = {skill: DIE_STEPS.get(points, "d12+4") for skill, points in effective_points.items()}
    return CharacterCreationResult(
        rank_name=rank_name,
        rank_index=rank_index,
        skill_dice=skill_dice,
        effective_skill_points=effective_points,
        superficial_health=superficial_health,
        extra_assets=progression_effects.extra_assets,
    )
