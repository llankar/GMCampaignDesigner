"""Rules engine for Savage Fate character creation."""

from __future__ import annotations

from dataclasses import dataclass

from .constants import DIE_STEPS, RANK_TABLE, SKILLS
from .points import compute_favorite_bonus


class CharacterCreationError(ValueError):
    """Raised when character creation payload violates Savage Fate rules."""


@dataclass
class CharacterCreationResult:
    rank_name: str
    rank_index: int
    skill_dice: dict[str, str]
    effective_skill_points: dict[str, int]
    superficial_health: int


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

    favorites = character_input.get("favorites") or []
    if len(favorites) != 6:
        raise CharacterCreationError("Il faut exactement 6 compétences favorites.")
    if len(set(favorites)) != 6:
        raise CharacterCreationError("Les compétences favorites doivent être uniques.")
    for skill in favorites:
        if skill not in SKILLS:
            raise CharacterCreationError(f"Compétence favorite invalide: {skill}")

    base_points = {skill: int((character_input.get("skills") or {}).get(skill, 0)) for skill in SKILLS}
    total_points = sum(base_points.values())
    if total_points != 15:
        raise CharacterCreationError(f"La somme des points de compétence doit être 15 (actuel: {total_points}).")
    for skill, points in base_points.items():
        if points < 0 or points > 5:
            raise CharacterCreationError(f"La compétence '{skill}' doit être entre 0 et 5 à la création.")

    advancements = int(character_input.get("advancements", 0))
    rank_name, rank_index, skill_cap_points = rank_from_advancements(advancements)

    bonus_points = compute_favorite_bonus(base_points, favorites)
    effective_points = {skill: base_points[skill] + bonus_points.get(skill, 0) for skill in SKILLS}

    for skill, pts in effective_points.items():
        if pts > skill_cap_points:
            raise CharacterCreationError(
                f"{skill} dépasse le cap du rang ({DIE_STEPS.get(skill_cap_points, 'd12+4')})."
            )

    feats = character_input.get("feats") or []
    if len(feats) != 2:
        raise CharacterCreationError("Il faut exactement 2 prouesses.")
    for feat in feats:
        options = feat.get("options") or []
        limitation = (feat.get("limitation") or "").strip()
        if len(options) != 3:
            raise CharacterCreationError("Chaque prouesse doit contenir exactement 3 options.")
        if not limitation:
            raise CharacterCreationError("Chaque prouesse doit définir une limitation.")

    equipment = character_input.get("equipment") or {}
    for key in ("weapon", "armor", "utility"):
        if key not in equipment:
            raise CharacterCreationError("L'équipement doit contenir arme, armure et utilitaire.")
    pe_alloc = {k: int(v) for k, v in (character_input.get("equipment_pe") or {}).items()}
    if sum(pe_alloc.get(k, 0) for k in ("weapon", "armor", "utility")) != 3:
        raise CharacterCreationError("Les PE de départ doivent totaliser 3 (1/1/1).")

    superficial_health = (10 if character_input.get("is_superhero") else 5) + 5

    skill_dice = {skill: DIE_STEPS.get(points, "d12+4") for skill, points in effective_points.items()}
    return CharacterCreationResult(
        rank_name=rank_name,
        rank_index=rank_index,
        skill_dice=skill_dice,
        effective_skill_points=effective_points,
        superficial_health=superficial_health,
    )
