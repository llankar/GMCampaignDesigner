from modules.pcs.character_creation.rules_engine import CharacterCreationError, build_character
from modules.pcs.character_creation.points import summarize_point_budgets


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
        "advancements": 0,
        "feats": [
            {"name": "Invisibilité", "options": ["Effet", "Durée", "Bonus"], "limitation": "1/scène"},
            {"name": "Feu", "options": ["Dommages", "Zone", "Portée"], "limitation": "Flamme requise"},
        ],
        "equipment": {"weapon": "Dague", "armor": "Manteau", "utility": "Grimoire"},
        "equipment_pe": {"weapon": 1, "armor": 1, "utility": 1},
    }


def test_build_character_ok():
    result = build_character(_payload())
    assert result.rank_name == "Novice"
    assert result.skill_dice["Combat"].startswith("d")


def test_build_character_requires_six_favorites():
    payload = _payload()
    payload["favorites"] = payload["favorites"][:5]
    try:
        build_character(payload)
        assert False, "Expected CharacterCreationError"
    except CharacterCreationError:
        pass


def test_favored_points_budget_summary_matches_rule():
    payload = _payload()
    summary = summarize_point_budgets(payload["skills"], payload["favorites"])
    expected_favored_spent = sum(payload["skills"][skill] for skill in payload["favorites"])
    expected_paid_favored_points = (expected_favored_spent + 1) // 2
    assert summary["spent_base"] == 10
    assert summary["remaining_base"] == 5
    assert summary["free_favored_points"] == expected_paid_favored_points
    assert summary["used_free_favored_points"] == expected_favored_spent - expected_paid_favored_points


def test_favored_points_budget_summary_without_bonus_when_less_than_two_favorites():
    payload = _payload()
    payload["favorites"] = ["Combat"]
    summary = summarize_point_budgets(payload["skills"], payload["favorites"])
    assert summary["spent_base"] == 15
    assert summary["free_favored_points"] == 0
    assert summary["used_free_favored_points"] == 0
