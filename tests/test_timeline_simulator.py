import sqlite3

import pytest

from db import db as db_module
from db.db import get_campaign_setting, set_campaign_setting
from modules.events.services.timeline_simulator import CampaignTimelineSimulator
from modules.generic.generic_model_wrapper import GenericModelWrapper
from modules.helpers.config_helper import ConfigHelper
from modules.helpers.template_loader import list_known_entities


@pytest.fixture
def campaign_db(monkeypatch, tmp_path):
    db_path = tmp_path / "campaign.db"

    original_get = ConfigHelper.get

    def fake_get(cls, section, key, fallback=None):
        if (section, key) == ("Database", "path"):
            return str(db_path)
        if (section, key) == ("Logging", "enabled"):
            return "false"
        return original_get(section, key, fallback=fallback)

    monkeypatch.setattr(ConfigHelper, "get", classmethod(fake_get))
    ConfigHelper._config = None
    ConfigHelper._config_mtime = None

    db_module.initialize_db()
    return db_path


def test_events_entity_is_built_in(campaign_db):
    assert "events" in list_known_entities()

    with sqlite3.connect(str(campaign_db)) as conn:
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='events'"
        ).fetchone()
    assert row is not None


def test_timeline_simulator_advances_world_state(campaign_db):
    set_campaign_setting("timeline_current_date", "2026-03-10")

    wrappers = {
        slug: GenericModelWrapper(slug, db_path=str(campaign_db))
        for slug in ("events", "factions", "npcs", "bases", "places", "scenarios", "maps", "clues", "informations")
    }

    wrappers["events"].save_items(
        [
            {
                "Name": "Dockside Meeting 2026-03-11 21:00",
                "Title": "Dockside Meeting",
                "Date": "2026-03-11",
                "StartTime": "21:00",
                "Type": "Operation",
                "Status": "Planned",
                "AutoResolve": True,
                "Places": ["Dockside"],
                "NPCs": ["Shade"],
                "Scenarios": ["Warehouse Raid"],
                "Maps": ["Harbor District"],
                "Clues": ["Smuggler Ledger"],
            }
        ]
    )
    wrappers["factions"].save_items(
        [
            {
                "Name": "Night Syndicate",
                "Description": "A criminal network expanding through the harbor.",
                "Agenda": "Tighten control over Dockside smuggling routes",
                "PlanStage": 1,
                "EscalationLevel": 1,
                "EscalationCadenceDays": 1,
                "NextEscalationDate": "2026-03-11",
                "ControlledPlaces": ["Dockside"],
                "ActiveScenarios": ["Warehouse Raid"],
                "Maps": ["Harbor District"],
                "Clues": ["Smuggler Ledger"],
            }
        ]
    )
    wrappers["npcs"].save_items(
        [
            {
                "Name": "Shade",
                "Role": "Fixer",
                "Description": "A careful lieutenant for the syndicate.",
                "IsVillain": True,
                "Agenda": "Coordinate the next smuggling run",
                "EscalationLevel": 0,
                "EscalationCadenceDays": 1,
                "NextEscalationDate": "2026-03-12",
                "CurrentLocation": "Safehouse",
                "LinkedScenarios": ["Warehouse Raid"],
                "Maps": ["Harbor District"],
                "Clues": ["Smuggler Ledger"],
                "MovementSchedule": [
                    {
                        "date": "2026-03-11",
                        "place": "Dockside",
                        "reason": "Meets the incoming smugglers",
                        "scenarios": ["Warehouse Raid"],
                        "maps": ["Harbor District"],
                        "clues": ["Smuggler Ledger"],
                    }
                ],
            }
        ]
    )
    wrappers["bases"].save_items(
        [
            {
                "Name": "Crew Safehouse",
                "Location": "Old Quarter",
                "Description": "A hidden base of operations.",
                "Maps": ["Harbor District"],
                "Projects": [
                    {
                        "name": "Ward Repairs",
                        "progress": 1,
                        "required": 2,
                        "daily_progress": 1,
                        "status": "active",
                        "scenario": ["Warehouse Raid"],
                        "maps": ["Harbor District"],
                        "clues": ["Smuggler Ledger"],
                    }
                ],
            }
        ]
    )
    wrappers["places"].save_items(
        [
            {
                "Name": "Dockside",
                "Description": "The busiest smuggling district in the city.",
                "Occupants": [],
            },
            {
                "Name": "Safehouse",
                "Description": "A quiet fallback location.",
                "Occupants": ["Shade"],
            },
        ]
    )
    wrappers["scenarios"].save_items(
        [
            {
                "Title": "Warehouse Raid",
                "Summary": "The crew may intercept a major delivery.",
                "Places": ["Dockside"],
                "NPCs": ["Shade"],
                "Objects": [],
            }
        ]
    )
    wrappers["maps"].save_items(
        [
            {
                "Name": "Harbor District",
                "Description": "A map of the docks and nearby alleys.",
            }
        ]
    )
    wrappers["clues"].save_items(
        [
            {
                "Name": "Smuggler Ledger",
                "Type": "Document",
                "Description": "An encrypted list of shipments.",
            }
        ]
    )
    wrappers["informations"].save_items([], replace=True)

    simulator = CampaignTimelineSimulator(wrappers=wrappers)
    result = simulator.advance_to("2026-03-12")

    assert result.days_advanced >= 1
    assert result.resolved_events == 1
    assert result.escalated_factions == 2
    assert result.escalated_villains == 1
    assert result.advanced_projects == 1
    assert result.npc_movements == 1
    assert result.change_count >= 4
    assert "Dockside Meeting" in result.gm_summary

    event = wrappers["events"].load_item_by_key("Dockside Meeting 2026-03-11 21:00")
    assert event["Status"] == "Resolved"
    assert "resolved automatically" in event["Resolution"]

    faction = wrappers["factions"].load_item_by_key("Night Syndicate")
    assert faction["PlanStage"] == 3
    assert faction["LastEscalationDate"] == "2026-03-12"

    npc = wrappers["npcs"].load_item_by_key("Shade")
    assert npc["CurrentLocation"] == "Dockside"
    assert npc["EscalationLevel"] == 1

    base = wrappers["bases"].load_item_by_key("Crew Safehouse")
    assert base["Projects"][0]["status"] == "completed"
    assert base["Projects"][0]["completed_date"] == "2026-03-11"

    dockside = wrappers["places"].load_item_by_key("Dockside")
    assert "Shade" in dockside["Occupants"]
    assert dockside["WorldStateChanges"]

    safehouse = wrappers["places"].load_item_by_key("Safehouse")
    assert "Shade" not in safehouse["Occupants"]

    scenario = wrappers["scenarios"].load_item_by_key("Warehouse Raid")
    assert scenario["LastTimelineUpdate"] == "2026-03-12"
    assert "Dockside Meeting" in scenario["GMNotes"]
    assert scenario["TimelineHistory"]

    campaign_map = wrappers["maps"].load_item_by_key("Harbor District")
    assert campaign_map["WorldStateChanges"]
    assert "Dockside Meeting" in campaign_map["DynamicNotes"]

    clue = wrappers["clues"].load_item_by_key("Smuggler Ledger")
    assert clue["Status"] == "Active"
    assert clue["DiscoveryDate"] == "2026-03-11"
    assert clue["WorldStateChanges"]

    assert get_campaign_setting("timeline_current_date") == "2026-03-12"
    assert "world-state changes" in get_campaign_setting("timeline_last_summary", "")
