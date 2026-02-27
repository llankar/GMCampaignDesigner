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
    bonus_skills = {skill: 0 for skill in skills}
    return {
        "name": "Ayla",
        "concept": "Mage exilée",
        "flaw": "Impulsive",
        "favorites": ["Combat", "Perception", "Sorcellerie", "Athlétisme", "Enquête", "Tir"],
        "skills": skills,
        "bonus_skills": bonus_skills,
        "advancements": 0,
        "feats": [
            {"name": "Invisibilité", "options": ["Effet", "Durée", "Bonus"], "limitation": "1/scène"},
            {"name": "Feu", "options": ["Dommages", "Zone", "Portée"], "limitation": "Flamme requise"},
        ],
        "equipment": {"weapon": "Dague", "armor": "Manteau", "utility": "Grimoire"},
        "equipment_pe": {"weapon": 1, "armor": 1, "utility": 1},
    }


def test_build_character_ok():
    payload = _payload()
    payload["bonus_skills"]["Combat"] = 2
    payload["bonus_skills"]["Perception"] = 2
    result = build_character(payload)
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
    payload["bonus_skills"]["Combat"] = 2
    payload["bonus_skills"]["Perception"] = 2
    summary = summarize_point_budgets(payload["skills"], payload["bonus_skills"], payload["favorites"])
    expected_generated = sum(payload["skills"][skill] for skill in payload["favorites"])
    assert summary["spent_base"] == 15
    assert summary["remaining_base"] == 0
    assert summary["generated_bonus"] == expected_generated
    assert summary["used_bonus"] == 4
    assert summary["remaining_bonus"] == expected_generated - 4


def test_bonus_points_cannot_exceed_generated_pool():
    payload = _payload()
    payload["bonus_skills"]["Combat"] = 20
    try:
        build_character(payload)
        assert False, "Expected CharacterCreationError"
    except CharacterCreationError as exc:
        assert "Points bonus insuffisants" in str(exc)


def test_bonus_points_only_on_favorites():
    payload = _payload()
    payload["bonus_skills"]["Artisanat"] = 1
    try:
        build_character(payload)
        assert False, "Expected CharacterCreationError"
    except CharacterCreationError as exc:
        assert "compétences favorites" in str(exc)


def test_advancement_choices_count_must_match_advancements():
    payload = _payload()
    payload["advancements"] = 2
    payload["advancement_choices"] = [{"type": "new_edge", "details": "Atout social"}]

    try:
        build_character(payload)
        assert False, "Expected CharacterCreationError"
    except CharacterCreationError as exc:
        assert "nombre de choix d'avancement" in str(exc)


def test_limited_advancement_cannot_repeat_same_rank():
    payload = _payload()
    payload["advancements"] = 2
    payload["advancement_choices"] = [
        {"type": "new_edge", "details": "Atout #1"},
        {"type": "new_edge", "details": "Atout #2"},
    ]

    try:
        build_character(payload)
        assert False, "Expected CharacterCreationError"
    except CharacterCreationError as exc:
        assert "une seule fois au rang" in str(exc)


def test_limited_advancement_can_repeat_on_new_rank():
    payload = _payload()
    payload["advancements"] = 5
    payload["advancement_choices"] = [
        {"type": "new_edge", "details": "Novice"},
        {"type": "equipment_points", "details": "Novice"},
        {"type": "new_skill", "details": "Novice"},
        {"type": "skill_improvement", "details": "Novice"},
        {"type": "new_edge", "details": "Expérimenté"},
    ]

    result = build_character(payload)
    assert result.rank_name == "Expérimenté"
