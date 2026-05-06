"""Tests for validation linked-field normalization."""

from src.validation.field_normalization import normalize_validator_reference_fields


def test_normalize_scenario_linked_fields_to_canonical_reference_fields():
    scenario = {
        "Title": "Opening Scene",
        "NPCs": ["Asha", {"Name": "Borin"}],
        "Places": ["Old Mill"],
        "Creatures": [{"id": "owlbear-1", "type": "creature"}],
    }

    normalized = normalize_validator_reference_fields("scenario", scenario)

    assert normalized["npc_refs"] == ["Asha", {"Name": "Borin"}]
    assert normalized["location_refs"] == ["Old Mill"]
    assert normalized["creature_refs"] == [{"id": "owlbear-1", "type": "creature"}]
    assert "NPCs" not in normalized
    assert "Places" not in normalized
    assert "Creatures" not in normalized


def test_normalize_campaign_linked_scenarios_to_scenario_refs():
    campaign = {"Name": "Dragonfall", "LinkedScenarios": ["Opening Scene"]}

    normalized = normalize_validator_reference_fields("campaign", campaign)

    assert normalized["scenario_refs"] == ["Opening Scene"]
    assert "LinkedScenarios" not in normalized


def test_normalize_preserves_existing_canonical_field_over_source_field():
    scenario = {"Title": "Opening Scene", "NPCs": ["Asha"], "npc_refs": ["Borin"]}

    normalized = normalize_validator_reference_fields("scenario", scenario)

    assert normalized["npc_refs"] == ["Borin"]
    assert "NPCs" not in normalized
