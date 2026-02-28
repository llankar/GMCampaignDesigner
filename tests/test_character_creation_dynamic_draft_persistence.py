from modules.pcs.character_creation.storage.payload_normalizer import normalize_draft_payload_for_form


def test_normalizer_preserves_dynamic_object_keys_for_equipment_and_purchases():
    payload = {
        "name": "Ayla",
        "equipment": {
            "weapon": "Dague",
            "armor": "Cuirasse",
            "utility": "Trousse",
            "object_4": "Relique",
            "object_5": "Drone",
        },
        "equipment_purchases": {
            "weapon": {"damage": 2, "pierce_armor": 0, "special_effect": 0, "skill_bonus": 0},
            "armor": {"armor": 1, "special_effect": 0, "skill_bonus": 0},
            "utility": {"special_effect": 1, "skill_bonus": 0},
            "object_4": {
                "damage": 0,
                "pierce_armor": 1,
                "armor": 0,
                "special_effect": 2,
                "skill_bonus": 0,
            },
            "object_5": {
                "damage": 1,
                "pierce_armor": 0,
                "armor": 1,
                "special_effect": 0,
                "skill_bonus": 2,
            },
        },
    }

    normalized = normalize_draft_payload_for_form(payload)

    assert normalized["equipment"]["object_4"] == "Relique"
    assert normalized["equipment"]["object_5"] == "Drone"
    assert normalized["equipment_purchases"]["object_4"]["special_effect"] == 2
    assert normalized["equipment_purchases"]["object_5"]["skill_bonus"] == 2
