"""Regression tests for campaign graph data."""

import importlib.util
import sys
from pathlib import Path


MODULE_PATH = Path("modules/campaigns/ui/graphical_display/data.py")
spec = importlib.util.spec_from_file_location("campaign_graph_data", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
sys.modules[spec.name] = module
spec.loader.exec_module(module)

build_campaign_graph_payload = module.build_campaign_graph_payload
build_campaign_option_index = module.build_campaign_option_index


def test_build_campaign_option_index_ignores_blank_names():
    """Verify that build campaign option index ignores blank names."""
    options, index = build_campaign_option_index([
        {"Name": ""},
        {"Name": "Duskfall"},
        {"Name": "Duskfall"},
        {"Name": "Iron Crown"},
    ])

    assert options == ["Duskfall", "Iron Crown"]
    assert set(index) == {"Duskfall", "Iron Crown"}


def test_build_campaign_graph_payload_includes_loose_threads(monkeypatch):
    """Verify that build campaign graph payload includes loose threads."""
    monkeypatch.setattr(module, "iter_scenario_link_fields", lambda: [("NPCs", "NPCs"), ("Places", "Places")])

    campaign = {
        "Name": "Duskfall",
        "Logline": "A haunted city trembles before a blood moon.",
        "Genre": "Gothic horror",
        "Tone": "Bleak",
        "Status": "In Progress",
        "LinkedScenarios": ["Moonlit Masquerade", "Catacomb Chase"],
        "Arcs": [
            {
                "name": "Red Revelations",
                "status": "in progress",
                "summary": "Peel back the cult's masks.",
                "objective": "Expose the high priest.",
                "scenarios": ["Moonlit Masquerade"],
            }
        ],
    }
    scenarios = [
        {
            "Title": "Moonlit Masquerade",
            "Summary": "A decadent ball where every smile hides a knife.",
            "NPCs": ["Lady Vesper"],
            "Places": ["Velvet Opera"],
        },
        {
            "Title": "Catacomb Chase",
            "Summary": "A pursuit beneath the city.",
            "NPCs": ["Brother Ash"],
            "Places": ["Old Catacombs"],
        },
    ]

    payload = build_campaign_graph_payload(campaign, scenarios)

    assert payload is not None
    assert payload.name == "Duskfall"
    assert [arc.name for arc in payload.arcs] == ["Red Revelations", "Loose Threads"]
    assert payload.arcs[0].scenarios[0].entity_links[0].name == "Lady Vesper"
    assert payload.arcs[1].scenarios[0].title == "Catacomb Chase"
    assert payload.linked_scenario_count == 2
