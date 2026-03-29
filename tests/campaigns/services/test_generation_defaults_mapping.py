import json

from modules.campaigns.services.generation_defaults_mapper import (
    DEFAULT_GENERATION_DEFAULTS_STATE,
    generation_defaults_payload_to_state,
    generation_defaults_state_to_payload,
)
from modules.campaigns.services.generation_defaults_service import (
    CAMPAIGN_GENERATION_DEFAULTS_KEY,
    CampaignGenerationDefaultsService,
)


def test_generation_defaults_payload_to_state_normalizes_lists_and_toggle():
    state = generation_defaults_payload_to_state(
        {
            "main_pc_factions": ["  Dawn Guard  ", "dawn guard", ""],
            "protected_factions": "Cobalt Circle",
            "forbidden_antagonist_factions": ["Night Court", None, " night court "],
            "allow_optional_conflicts": 0,
        }
    )

    assert state == {
        "main_pc_factions": ["Dawn Guard"],
        "protected_factions": ["Cobalt Circle"],
        "forbidden_antagonist_factions": ["Night Court"],
        "allow_optional_conflicts": False,
    }


def test_generation_defaults_state_to_payload_round_trip():
    initial_state = {
        "main_pc_factions": ["Silver Banner", "Silver Banner", " Wayfinders "],
        "protected_factions": ["Archive Keepers"],
        "forbidden_antagonist_factions": ["Iron Claw"],
        "allow_optional_conflicts": True,
    }

    payload = generation_defaults_state_to_payload(initial_state)
    round_trip = generation_defaults_payload_to_state(payload)

    assert payload == round_trip


def test_generation_defaults_service_save_and_load_uses_json_payload():
    stored = {}

    def _get_setting(key, default=None):
        return stored.get(key, default)

    def _set_setting(key, value):
        stored[key] = value

    service = CampaignGenerationDefaultsService(get_setting=_get_setting, set_setting=_set_setting)
    saved_payload = service.save(
        {
            "main_pc_factions": ["Wardens"],
            "protected_factions": ["Free Cities"],
            "forbidden_antagonist_factions": ["Ash League"],
            "allow_optional_conflicts": False,
        }
    )

    assert saved_payload["main_pc_factions"] == ["Wardens"]
    assert CAMPAIGN_GENERATION_DEFAULTS_KEY in stored

    serialized = json.loads(stored[CAMPAIGN_GENERATION_DEFAULTS_KEY])
    assert serialized == saved_payload
    assert service.load() == saved_payload


def test_generation_defaults_service_load_falls_back_for_invalid_json():
    service = CampaignGenerationDefaultsService(
        get_setting=lambda _key, _default=None: "{not-valid-json}",
        set_setting=lambda _key, _value: None,
    )

    assert service.load() == DEFAULT_GENERATION_DEFAULTS_STATE
