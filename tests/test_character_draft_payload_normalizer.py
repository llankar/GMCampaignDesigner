from modules.pcs.character_creation.storage.payload_normalizer import normalize_draft_payload_for_form


def test_normalizer_maps_nested_equipment_to_flat_form_fields():
    payload = {
        "name": "Ayla",
        "equipment": {"weapon": "Dague", "armor": "Manteau", "utility": "Grimoire"},
        "equipment_pe": {"weapon": 2, "armor": 1, "utility": 3},
    }

    normalized = normalize_draft_payload_for_form(payload)

    assert normalized["weapon"] == "Dague"
    assert normalized["armor"] == "Manteau"
    assert normalized["utility"] == "Grimoire"
    assert normalized["weapon_pe"] == 2
    assert normalized["armor_pe"] == 1
    assert normalized["utility_pe"] == 3


def test_normalizer_reads_legacy_equipement_keys():
    payload = {
        "equipement": {"weapon": "Arc", "armor": "Cuir", "utility": "Trousse"},
        "equipement_pe": {"weapon": 1, "armor": 2, "utility": 1},
    }

    normalized = normalize_draft_payload_for_form(payload)

    assert normalized["weapon"] == "Arc"
    assert normalized["armor"] == "Cuir"
    assert normalized["utility"] == "Trousse"
    assert normalized["weapon_pe"] == 1
    assert normalized["armor_pe"] == 2
    assert normalized["utility_pe"] == 1
