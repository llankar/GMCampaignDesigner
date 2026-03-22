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
    options, index = build_campaign_option_index([
        {"Name": ""},
        {"Name": "Duskfall"},
        {"Name": "Duskfall"},
        {"Name": "Iron Crown"},
    ])

    assert options == ["Duskfall", "Iron Crown"]
    assert set(index) == {"Duskfall", "Iron Crown"}


def test_build_campaign_graph_payload_includes_loose_threads(monkeypatch):
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


def test_build_campaign_graph_payload_reads_link_fields_once(monkeypatch):
    calls = []

    def fake_iter_fields():
        calls.append('called')
        return [("NPCs", "NPCs")]

    monkeypatch.setattr(module, "iter_scenario_link_fields", fake_iter_fields)

    campaign = {
        "Name": "Starfall",
        "LinkedScenarios": ["Scene One", "Scene Two", "Scene Three"],
        "Arcs": [
            {
                "name": "Opening",
                "scenarios": ["Scene One", "Scene Two"],
            }
        ],
    }
    scenarios = [
        {"Title": "Scene One", "NPCs": ["Iris"]},
        {"Title": "Scene Two", "NPCs": ["Morrow"]},
        {"Title": "Scene Three", "NPCs": ["Vale"]},
    ]

    payload = build_campaign_graph_payload(campaign, scenarios)

    assert payload is not None
    assert len(calls) == 1
    assert payload.arcs[0].scenarios[1].entity_links[0].name == "Morrow"
    assert payload.arcs[1].scenarios[0].entity_links[0].name == "Vale"
