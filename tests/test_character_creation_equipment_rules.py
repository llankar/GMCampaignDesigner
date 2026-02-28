from modules.pcs.character_creation.equipment import (
    available_equipment_points,
    equipment_points_from_advancement_choices,
    max_pe_per_object,
)
from modules.pcs.character_creation.rules_engine import CharacterCreationError, build_character


def _payload():
    skills = {
        "Artisanat": 0,
        "Athlétisme": 2,
        "Combat": 3,
        "Commandement": 0,
        "Discrétion": 1,
        "Enquête": 1,
        "Érudition": 1,
        "Informatique": 0,
        "Jeu": 0,
        "Médecine": 0,
        "Perception": 2,
        "Persuasion": 1,
        "Pilotage": 1,
        "Relation": 0,
        "Représentation": 0,
        "Ressource": 0,
        "Sorcellerie": 1,
        "Subornation": 0,
        "Survie": 1,
        "Technologie": 0,
        "Tir": 1,
        "Vol": 0,
    }
    return {
        "name": "Ayla",
        "concept": "Mage exilée",
        "flaw": "Impulsive",
        "favorites": ["Combat", "Perception", "Sorcellerie", "Athlétisme", "Enquête", "Tir"],
        "skills": skills,
        "bonus_skills": {skill: 0 for skill in skills},
        "advancements": 0,
        "feats": [
            {"name": "Invisibilité", "options": ["Effet", "Durée", "Bonus"], "limitation": "1/scène"},
            {"name": "Feu", "options": ["Dommages", "Zone", "Portée"], "limitation": "Flamme requise"},
        ],
        "equipment": {"weapon": "Dague", "armor": "Manteau", "utility": "Grimoire"},
        "equipment_pe": {"weapon": 1, "armor": 1, "utility": 1},
    }


def test_equipment_points_use_rank_not_prowess_count():
    choices = [
        {"type": "equipment_points", "details": "N1"},
        {"type": "prowess_points", "details": "+2"},
        {"type": "equipment_points", "details": "N3"},
        {"type": "skill_improvement", "details": "Combat"},
        {"type": "equipment_points", "details": "N5"},
    ]

    assert equipment_points_from_advancement_choices(choices) == (4 + 1) + (4 + 1) + (4 + 2)
    assert available_equipment_points(choices) == 3 + (4 + 1) + (4 + 1) + (4 + 2)


def test_equipment_per_object_cap_depends_on_rank():
    assert max_pe_per_object(0) == 2
    assert max_pe_per_object(4) == 3
    assert max_pe_per_object(8) == 4


def test_build_character_rejects_equipment_over_rank_cap():
    payload = _payload()
    payload["equipment_pe"] = {"weapon": 3, "armor": 0, "utility": 0}
    try:
        build_character(payload)
        assert False, "Expected CharacterCreationError"
    except CharacterCreationError as exc:
        assert "plafond de PE" in str(exc)


def test_build_character_accepts_allocating_less_than_available_equipment_points():
    payload = _payload()
    payload["advancements"] = 1
    payload["advancement_choices"] = [{"type": "equipment_points", "details": "Arsenal"}]
    payload["equipment_pe"] = {"weapon": 1, "armor": 1, "utility": 1}

    result = build_character(payload)
    assert result.rank_name == "Novice"


def test_build_character_validates_equipment_purchase_distribution():
    payload = _payload()
    payload["equipment_purchases"] = {
        "weapon": {"damage": 1, "pierce_armor": 0, "special_effect": 0, "skill_bonus": 0},
        "armor": {"armor": 1, "special_effect": 0, "skill_bonus": 0},
        "utility": {"special_effect": 1, "skill_bonus": 0},
    }

    result = build_character(payload)
    assert result.rank_name == "Novice"
