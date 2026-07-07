"""Tests for AI-generated scenario entity persistence."""

import sqlite3

from modules.scenarios.services.generated_entity_persistence import (
    GeneratedScenarioEntityPersistence,
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

