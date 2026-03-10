import sqlite3

from db.db import load_schema_from_json
from modules.ai.automation.auto_generation_service import AutoGenerationService
from modules.generic.generic_list_view import GenericListView
from modules.generic.generic_model_wrapper import GenericModelWrapper
from modules.helpers.template_loader import load_entity_definitions, load_template


def _create_table_from_template(db_path, entity_slug):
    schema = load_schema_from_json(entity_slug)
    cols = ", ".join(f"{name} {kind}" for name, kind in schema)
    pk = schema[0][0]
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            f"CREATE TABLE {entity_slug} ({cols}, PRIMARY KEY({pk}))"
        )
        conn.commit()
    finally:
        conn.close()


def test_bases_entity_is_registered_and_template_has_expected_links():
    definitions = load_entity_definitions()
    assert definitions["bases"]["label"] == "Bases"

    template = load_template("bases")
    fields = {field["name"]: field for field in template["fields"]}

    assert fields["Maps"]["linked_type"] == "Maps"
    assert fields["NPCs"]["linked_type"] == "NPCs"
    assert fields["Factions"]["linked_type"] == "Factions"
    assert fields["DowntimeHooks"]["type"] == "list_longtext"


def test_bases_persistence_round_trip(tmp_path):
    db_path = tmp_path / "bases.db"
    _create_table_from_template(str(db_path), "bases")
    wrapper = GenericModelWrapper("bases", db_path=str(db_path))

    wrapper.save_item(
        {
            "Name": "Skyhold",
            "Location": "Storm Coast",
            "Upgrades": ["Ballista Tower", "Arcane Workshop"],
            "Staff": ["Quartermaster Vale", "Scout Nera"],
            "Stores": ["Black powder", "Rations"],
            "Threats": ["Harpy raids"],
            "Defenses": ["Curtain wall", "Watch beacons"],
            "Maps": ["Cliff Fortress"],
            "NPCs": ["Quartermaster Vale"],
            "Factions": ["Wardens"],
            "DowntimeHooks": ["Repair the breach", "Train new recruits"],
            "Notes": "Primary field headquarters.",
        }
    )

    loaded = wrapper.load_item_by_key("Skyhold")

    assert loaded["Location"] == "Storm Coast"
    assert loaded["Maps"] == ["Cliff Fortress"]
    assert loaded["NPCs"] == ["Quartermaster Vale"]
    assert loaded["Factions"] == ["Wardens"]
    assert loaded["DowntimeHooks"] == ["Repair the breach", "Train new recruits"]


def test_bases_link_groups_include_maps_npcs_and_factions():
    view = GenericListView.__new__(GenericListView)
    view.template = load_template("bases")

    groups = view._collect_linked_entities(
        {
            "Name": "Redoubt",
            "Maps": ["Upper Ward", "Vault"],
            "NPCs": ["Mira", "Tolan"],
            "Factions": ["Night Watch"],
        }
    )

    assert list(groups["maps"]) == ["Upper Ward", "Vault"]
    assert list(groups["npcs"]) == ["Mira", "Tolan"]
    assert list(groups["factions"]) == ["Night Watch"]


def test_parent_context_includes_base_details_for_generation():
    service = AutoGenerationService()

    context = service._build_parent_context(
        "bases",
        {
            "Name": "Hearthspire",
            "Description": "A fortified inn repurposed as the party's domain.",
            "Location": "Ash Market",
            "Upgrades": ["Signal lanterns", "Hidden vault"],
            "DowntimeHooks": ["Broker peace with the dock guild"],
            "NPCs": ["Marrow"],
            "Factions": ["Dock Guild"],
        },
    )

    assert "Parent bases: Hearthspire" in context
    assert "Location: Ash Market" in context
    assert "Upgrades: Signal lanterns, Hidden vault" in context
    assert "DowntimeHooks: Broker peace with the dock guild" in context
    assert "NPCs: Marrow" in context
