"""Equipment point budgets and allocation validation helpers."""

from __future__ import annotations

from ..constants import RANK_TABLE

EQUIPMENT_KEYS = ("weapon", "armor", "utility")
BASE_EQUIPMENT_POINTS = 3


class EquipmentValidationError(ValueError):
    """Raised when equipment payload does not satisfy character creation rules."""


def rank_index_from_advancements(advancements: int) -> int:
    for idx, (_, end, _, _) in enumerate(RANK_TABLE):
        if advancements <= end:
            return idx
    return len(RANK_TABLE) - 1


def equipment_points_from_advancement_choices(advancement_choices: list[dict]) -> int:
    bonus = 0
    for index, raw_choice in enumerate(advancement_choices, start=1):
        choice_type = (raw_choice or {}).get("type", "").strip()
        if choice_type != "equipment_points":
            continue
        bonus += 4 + rank_index_from_advancements(index)
    return bonus


def available_equipment_points(advancement_choices: list[dict]) -> int:
    return BASE_EQUIPMENT_POINTS + equipment_points_from_advancement_choices(advancement_choices)


def max_pe_per_object(advancements: int) -> int:
    return 1 + rank_index_from_advancements(advancements)


def _coerce_int(value) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError) as exc:
        raise EquipmentValidationError("Les champs PE doivent être des nombres entiers.") from exc


def validate_equipment(character_input: dict, advancements: int, advancement_choices: list[dict]) -> None:
    equipment = character_input.get("equipment") or {}
    for key in EQUIPMENT_KEYS:
        if key not in equipment:
            raise EquipmentValidationError("L'équipement doit contenir arme, armure et utilitaire.")

    pe_alloc = {key: _coerce_int((character_input.get("equipment_pe") or {}).get(key, 0)) for key in EQUIPMENT_KEYS}
    total_available = available_equipment_points(advancement_choices)
    max_per_object = max_pe_per_object(advancements)

    if sum(pe_alloc.values()) > total_available:
        raise EquipmentValidationError(f"Les PE alloués ne peuvent pas dépasser {total_available}.")

    for key, value in pe_alloc.items():
        if value < 0:
            raise EquipmentValidationError(f"Les PE de {key} ne peuvent pas être négatifs.")
        if value > max_per_object:
            raise EquipmentValidationError(f"{key} dépasse le plafond de PE ({max_per_object}).")

    purchases = character_input.get("equipment_purchases") or {}
    if not purchases:
        return

    purchase_rules = {
        "weapon": ("damage", "pierce_armor", "special_effect", "skill_bonus"),
        "armor": ("armor", "special_effect", "skill_bonus"),
        "utility": ("special_effect", "skill_bonus"),
    }

    for key, allowed_fields in purchase_rules.items():
        object_purchases = purchases.get(key) or {}
        spent = sum(_coerce_int(object_purchases.get(field, 0)) for field in allowed_fields)
        if spent != pe_alloc[key]:
            raise EquipmentValidationError(
                f"Les achats de {key} doivent consommer exactement {pe_alloc[key]} PE (actuel: {spent})."
            )

        skill_bonus_cost = _coerce_int(object_purchases.get("skill_bonus", 0))
        if skill_bonus_cost % 2 != 0:
            raise EquipmentValidationError(f"Le bonus de compétence de {key} coûte 2 PE par palier.")
