"""Tests for AI-generated scenario entity persistence."""

import sqlite3

from modules.scenarios.services.generated_entity_persistence import (
    GeneratedScenarioEntityPersistence,
    scenario_entity_names,
)
from modules.generic.generic_model_wrapper import GenericModelWrapper


def _create_campaign_db(path):
    conn = sqlite3.connect(path)
    try:
        conn.execute("CREATE TABLE npcs (Name TEXT PRIMARY KEY)")
        conn.execute("CREATE TABLE places (Name TEXT PRIMARY KEY)")
        conn.commit()
    finally:
        conn.close()


def test_save_missing_entities_creates_npcs_and_places(tmp_path):
    """Verify that generated scenario references become real entity records."""
    db_path = tmp_path / "campaign.db"
    _create_campaign_db(db_path)

    persistence = GeneratedScenarioEntityPersistence(
        npc_wrapper=GenericModelWrapper("npcs", db_path=str(db_path)),
        place_wrapper=GenericModelWrapper("places", db_path=str(db_path)),
    )

    result = persistence.save_missing_entities(
        {
            "Title": "The Harbor Job",
            "NPCs": ["Captain Mira", "Old Fenwick"],
            "Places": ["Blackstone Harbor"],
        }
    )

    assert result.npcs_created == ["Captain Mira", "Old Fenwick"]
    assert result.places_created == ["Blackstone Harbor"]

    npcs = GenericModelWrapper("npcs", db_path=str(db_path)).load_items()
    places = GenericModelWrapper("places", db_path=str(db_path)).load_items()

    assert {npc["Name"] for npc in npcs} == {"Captain Mira", "Old Fenwick"}
    assert {place["Name"] for place in places} == {"Blackstone Harbor"}
    assert places[0]["NPCs"] == ["Captain Mira", "Old Fenwick"]


def test_save_missing_entities_keeps_existing_records(tmp_path):
    """Verify that existing entity records are not overwritten."""
    db_path = tmp_path / "campaign.db"
    _create_campaign_db(db_path)
    npc_wrapper = GenericModelWrapper("npcs", db_path=str(db_path))
    place_wrapper = GenericModelWrapper("places", db_path=str(db_path))
    npc_wrapper.save_item(
        {"Name": "Captain Mira", "Description": "Existing details"},
        key_field="Name",
    )

    persistence = GeneratedScenarioEntityPersistence(
        npc_wrapper=npc_wrapper,
        place_wrapper=place_wrapper,
    )

    result = persistence.save_missing_entities(
        {
            "Title": "The Harbor Job",
            "NPCs": ["Captain Mira", "Old Fenwick"],
            "Places": [],
        }
    )

    assert result.npcs_created == ["Old Fenwick"]

    saved_mira = npc_wrapper.load_item_by_key("Captain Mira", key_field="Name")
    assert saved_mira["Description"] == "Existing details"


def test_save_missing_entities_uses_structured_ai_payload(tmp_path):
    """Verify generated entities reuse PDF-import-style rich records when available."""
    db_path = tmp_path / "campaign.db"
    _create_campaign_db(db_path)
    npc_wrapper = GenericModelWrapper("npcs", db_path=str(db_path))
    place_wrapper = GenericModelWrapper("places", db_path=str(db_path))

    persistence = GeneratedScenarioEntityPersistence(
        npc_wrapper=npc_wrapper,
        place_wrapper=place_wrapper,
    )
    parsed_payload = {
        "Title": "Juliet's Fall",
        "NPCs": [
            {
                "Name": "Juliet Vale",
                "Role": "Fallen heir",
                "Description": "A poised aristocrat hiding panic behind perfect etiquette.",
                "Motivation": "Recover the ledger before her enemies do.",
            }
        ],
        "Places": [
            {
                "Name": "Grand Ballroom",
                "Description": "A rain-streaked event hall with cracked marble and champagne towers.",
                "Secrets": "The balcony is rigged to collapse.",
                "NPCs": ["Juliet Vale"],
            }
        ],
    }

    result = persistence.save_missing_entities(
        {
            "Title": "Juliet's Fall",
            "NPCs": scenario_entity_names(parsed_payload["NPCs"]),
            "Places": scenario_entity_names(parsed_payload["Places"]),
        },
        parsed_payload,
    )

    assert result.npcs_created == ["Juliet Vale"]
    assert result.places_created == ["Grand Ballroom"]

    saved_npc = npc_wrapper.load_item_by_key("Juliet Vale", key_field="Name")
    saved_place = place_wrapper.load_item_by_key("Grand Ballroom", key_field="Name")

    assert saved_npc["Role"] == "Fallen heir"
    assert "poised aristocrat" in saved_npc["Description"]["text"]
    assert "Recover the ledger" in saved_npc["Motivation"]["text"]
    assert "rain-streaked event hall" in saved_place["Description"]["text"]
    assert saved_place["NPCs"] == ["Juliet Vale"]
    assert "balcony is rigged" in saved_place["Secrets"]["text"]


def test_save_missing_entities_uses_scene_text_instead_of_generic_fallback(tmp_path):
    """Verify bare generated entities are enriched from generated scene text."""
    db_path = tmp_path / "campaign.db"
    _create_campaign_db(db_path)
    npc_wrapper = GenericModelWrapper("npcs", db_path=str(db_path))
    place_wrapper = GenericModelWrapper("places", db_path=str(db_path))

    persistence = GeneratedScenarioEntityPersistence(
        npc_wrapper=npc_wrapper,
        place_wrapper=place_wrapper,
    )
    parsed_payload = {
        "Title": "Death in Love",
        "Summary": "A doomed wedding hides a murder pact.",
        "NPCs": ["Juliet Vale"],
        "Places": ["Grand Ballroom"],
        "Scenes": [
            {
                "Title": "The Poisoned Toast",
                "Text": "Juliet Vale trembles while accusing the masked violinist. The Grand Ballroom erupts as guests notice the poisoned glass.",
                "NPCs": ["Juliet Vale"],
                "Places": ["Grand Ballroom"],
            }
        ],
    }

    persistence.save_missing_entities(
        {
            "Title": "Death in Love",
            "NPCs": scenario_entity_names(parsed_payload["NPCs"]),
            "Places": scenario_entity_names(parsed_payload["Places"]),
            "Scenes": parsed_payload["Scenes"],
        },
        parsed_payload,
    )

    saved_npc = npc_wrapper.load_item_by_key("Juliet Vale", key_field="Name")
    saved_place = place_wrapper.load_item_by_key("Grand Ballroom", key_field="Name")

    assert "Generated from AI scenario" not in saved_npc["Description"]["text"]
    assert "Generated from AI scenario" not in saved_place["Description"]["text"]
    assert saved_npc["Role"] != "Scenario NPC"
    assert "Poisoned Toast" in saved_npc["Description"]["text"]
    assert "poisoned glass" in saved_place["Description"]["text"]


def test_save_missing_entities_moves_npc_atouts_from_description_to_traits(tmp_path):
    """Verify generated NPC Atouts are saved in Traits, not Description."""
    db_path = tmp_path / "campaign.db"
    _create_campaign_db(db_path)
    npc_wrapper = GenericModelWrapper("npcs", db_path=str(db_path))

    persistence = GeneratedScenarioEntityPersistence(
        npc_wrapper=npc_wrapper,
        place_wrapper=GenericModelWrapper("places", db_path=str(db_path)),
    )
    parsed_payload = {
        "Title": "Glass Wolves",
        "NPCs": [
            {
                "Name": "Mara Voss",
                "Description": "Tall smuggler in a red synth-leather coat with silver eyes.\nAtouts:\n- Quick draw\n- Knows every dock camera",
                "Traits": "Restless and charming",
            }
        ],
    }

    persistence.save_missing_entities(
        {"Title": "Glass Wolves", "NPCs": ["Mara Voss"], "Places": []},
        parsed_payload,
    )

    saved_npc = npc_wrapper.load_item_by_key("Mara Voss", key_field="Name")
    assert "Atouts" not in saved_npc["Description"]["text"]
    assert "Tall smuggler" in saved_npc["Description"]["text"]
    assert "Restless and charming" in saved_npc["Traits"]["text"]
    assert "Atouts" in saved_npc["Traits"]["text"]
    assert "Quick draw" in saved_npc["Traits"]["text"]
