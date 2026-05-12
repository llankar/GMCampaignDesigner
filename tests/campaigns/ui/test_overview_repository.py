"""Tests for the lightweight campaign overview repository."""

import json
import sqlite3

from modules.campaigns.ui.graphical_display.services.overview_repository import CampaignOverviewRepository


def test_list_campaigns_loads_only_overview_columns_with_focus(tmp_path):
    """Campaign list should skip editor-only columns and include saved overview focus."""
    db_path = tmp_path / "campaign.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE campaigns (
                Name TEXT PRIMARY KEY,
                Logline TEXT,
                Genre TEXT,
                Tone TEXT,
                Status TEXT,
                Setting TEXT,
                MainObjective TEXT,
                Stakes TEXT,
                Themes TEXT,
                LinkedScenarios TEXT,
                Arcs TEXT,
                Notes TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE campaign_config (
                campaign_name TEXT PRIMARY KEY,
                overview_selected_arc TEXT,
                overview_selected_scenario TEXT
            )
            """
        )
        conn.execute(
            """
            INSERT INTO campaigns (
                Name, Logline, Genre, Tone, Status, Setting, MainObjective,
                Stakes, Themes, LinkedScenarios, Arcs, Notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "Dragonfall",
                "Stop the wyrm cult.",
                "Fantasy",
                "Heroic",
                "Active",
                "Ash Coast",
                "Seal the rift",
                "A city burns",
                "Duty",
                json.dumps(["Opening Gambit"]),
                json.dumps([{"name": "Act I", "scenarios": ["Opening Gambit"]}]),
                "Large editor-only notes should not be loaded by the dashboard.",
            ),
        )
        conn.execute(
            "INSERT INTO campaign_config VALUES (?, ?, ?)",
            ("Dragonfall", "Act I", "Opening Gambit"),
        )

    campaigns = CampaignOverviewRepository(db_path=str(db_path)).list_campaigns_for_overview()

    assert campaigns == [
        {
            "Name": "Dragonfall",
            "Logline": "Stop the wyrm cult.",
            "Genre": "Fantasy",
            "Tone": "Heroic",
            "Status": "Active",
            "Setting": "Ash Coast",
            "MainObjective": "Seal the rift",
            "Stakes": "A city burns",
            "Themes": "Duty",
            "LinkedScenarios": ["Opening Gambit"],
            "Arcs": [{"name": "Act I", "scenarios": ["Opening Gambit"]}],
            "overview_selected_arc": "Act I",
            "overview_selected_scenario": "Opening Gambit",
        }
    ]


def test_list_linked_scenarios_loads_only_campaign_references_and_payload_fields(tmp_path):
    """Scenario loading should be scoped to the selected campaign and dashboard fields."""
    db_path = tmp_path / "campaign.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE scenarios (
                Title TEXT PRIMARY KEY,
                Summary TEXT,
                Briefing TEXT,
                Objective TEXT,
                Hook TEXT,
                Stakes TEXT,
                Scenes TEXT,
                Secrets TEXT,
                Places TEXT,
                Factions TEXT,
                Notes TEXT
            )
            """
        )
        conn.execute(
            """
            INSERT INTO scenarios (
                Title, Summary, Briefing, Objective, Hook, Stakes, Scenes,
                Secrets, Places, Factions, Notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "Opening Gambit",
                "Begin at the gala.",
                "Brief the GM.",
                "Find the spy",
                "A masked warning",
                "The spy escapes",
                json.dumps([{"Title": "Gala"}]),
                "The duke is compromised.",
                json.dumps(["Moon Palace"]),
                json.dumps(["Glass Court"]),
                "Editor-only notes",
            ),
        )
        conn.execute(
            """
            INSERT INTO scenarios (
                Title, Summary, Briefing, Objective, Hook, Stakes, Scenes,
                Secrets, Places, Factions, Notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "Unlinked Scenario",
                "Should not load.",
                "",
                "",
                "",
                "",
                json.dumps([]),
                "",
                json.dumps([]),
                json.dumps([]),
                "",
            ),
        )

    campaign = {
        "LinkedScenarios": ["Opening Gambit"],
        "Arcs": [{"name": "Act I", "scenarios": ["Opening Gambit"]}],
    }
    scenarios = CampaignOverviewRepository(db_path=str(db_path)).load_scenarios_for_campaign(campaign)

    assert scenarios == [
        {
            "Title": "Opening Gambit",
            "Summary": "Begin at the gala.",
            "Briefing": "Brief the GM.",
            "Objective": "Find the spy",
            "Hook": "A masked warning",
            "Stakes": "The spy escapes",
            "Scenes": [{"Title": "Gala"}],
            "Secrets": "The duke is compromised.",
            "Places": ["Moon Palace"],
            "Factions": ["Glass Court"],
        }
    ]
