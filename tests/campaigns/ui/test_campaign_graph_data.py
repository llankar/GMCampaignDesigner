"""Regression tests for campaign graph data."""

import importlib.util
import sys
from pathlib import Path

from modules.campaigns.shared.progress import campaign_progress_from_arcs


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
    calls = []

    def _iter_link_fields():
        calls.append(1)
        return [("NPCs", "NPCs"), ("Places", "Places")]

    monkeypatch.setattr(module, "iter_scenario_link_fields", _iter_link_fields)

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
    assert len(calls) == 1


def test_build_campaign_graph_payload_canonicalizes_scenario_statuses(monkeypatch):
    """Verify graph payload scenario status defaults and canonicalization are compatibility-safe."""
    monkeypatch.setattr(module, "iter_scenario_link_fields", lambda: [])
    campaign = {
        "Name": "Status Campaign",
        "LinkedScenarios": ["Known", "Blank", "Missing"],
        "Arcs": [
            {
                "name": "Opening",
                "status": "Completed",
                "scenarios": ["Known", "Blank", "Missing", "Absent"],
            }
        ],
    }
    scenarios = [
        {"Title": "Known", "Summary": "Has alias.", "Status": "running"},
        {"Title": "Blank", "Summary": "Blank status.", "Status": ""},
        {"Title": "Missing", "Summary": "No status."},
    ]

    payload = build_campaign_graph_payload(campaign, scenarios)

    assert payload is not None
    assert [scenario.status for scenario in payload.arcs[0].scenarios] == [
        "In Progress",
        "Planned",
        "Planned",
        "Planned",
    ]
    assert payload.arcs[0].scenarios[-1].record_exists is False


def test_build_campaign_graph_payload_preserves_completed_status_for_progress(monkeypatch):
    """Verify completed scenario Status survives graph payload build and counts as progress."""
    monkeypatch.setattr(module, "iter_scenario_link_fields", lambda: [])
    campaign = {
        "Name": "Completion Campaign",
        "LinkedScenarios": ["Finale"],
        "Arcs": [{"name": "Final Act", "scenarios": ["Finale"]}],
    }
    scenarios = [{"Title": "Finale", "Summary": "The last scene.", "Status": "Completed"}]

    payload = build_campaign_graph_payload(campaign, scenarios)

    assert payload is not None
    assert payload.arcs[0].scenarios[0].status == "Completed"
    assert campaign_progress_from_arcs(payload.arcs) == 1.0


def test_build_campaign_graph_payload_indexes_only_referenced_scenarios(monkeypatch):
    """Verify graph payload indexing ignores full-list scenarios not referenced by the campaign."""
    monkeypatch.setattr(module, "iter_scenario_link_fields", lambda: [])
    original_builder = module._build_scenario_payload
    indexed_titles = []

    def _spy_build_scenario_payload(title, scenario_index, link_fields):
        indexed_titles.append(set(scenario_index))
        return original_builder(title, scenario_index, link_fields)

    monkeypatch.setattr(module, "_build_scenario_payload", _spy_build_scenario_payload)

    campaign = {
        "Name": "Lean Campaign",
        "LinkedScenarios": ["Needed Scenario"],
        "Arcs": [{"name": "Act I", "scenarios": ["Needed Scenario"]}],
    }
    scenarios = [
        {"Title": "Needed Scenario", "Summary": "Keep this row."},
        {"Title": "Unlinked Scenario", "Summary": "Do not index this row."},
    ]

    payload = build_campaign_graph_payload(campaign, scenarios)

    assert payload is not None
    assert indexed_titles == [{"Needed Scenario"}]
    assert payload.arcs[0].scenarios[0].record_exists is True

def test_build_campaign_graph_payload_repairs_legacy_mojibake(monkeypatch):
    """Verify that legacy mojibake text is repaired during overview payload build."""
    monkeypatch.setattr(module, "iter_scenario_link_fields", lambda: [])

    clean_name = "PharmaCorp Prot\u00e9ger"
    clean_logline = "Planned \u2022 9 scenarios"
    clean_summary = "Valut\u00e9 de la mission."
    clean_briefing = "Prot\u00e9ger le site."

    campaign = {
        "Name": clean_name.encode("utf-8").decode("cp1252").encode("utf-8").decode("cp1252"),
        "Logline": clean_logline.encode("utf-8").decode("cp1252"),
        "Genre": "Cyberpunk",
        "Tone": "Bleak",
        "Status": "Planned",
        "LinkedScenarios": ["Retrouver agent fugueur Miyazato Hokichi"],
        "Arcs": [
            {
                "name": "PharmaCorp Protection & Espionage",
                "status": "Planned",
                "summary": "Secure the facility.",
                "objective": "Hold the line.",
                "scenarios": ["Retrouver agent fugueur Miyazato Hokichi"],
            }
        ],
    }
    scenarios = [
        {
            "Title": "Retrouver agent fugueur Miyazato Hokichi",
            "Summary": clean_summary.encode("utf-8").decode("cp1252"),
            "Briefing": clean_briefing.encode("utf-8").decode("cp1252"),
        }
    ]

    payload = build_campaign_graph_payload(campaign, scenarios)

    assert payload is not None
    assert payload.name == clean_name
    assert payload.logline == clean_logline
    assert payload.arcs[0].scenarios[0].summary == clean_summary
    assert payload.arcs[0].scenarios[0].briefing == clean_briefing
    assert payload.arcs[0].scenarios[0].title == "Retrouver agent fugueur Miyazato Hokichi"

def test_build_campaign_graph_payload_truncates_oversized_display_text(monkeypatch):
    """Verify oversized imported text is bounded before reaching Tk widgets."""
    monkeypatch.setattr(module, "iter_scenario_link_fields", lambda: [("NPCs", "NPCs")])

    huge_label = "A" * 1_000
    huge_body = "B" * 12_000
    campaign = {
        "Name": huge_label,
        "Logline": huge_body,
        "LinkedScenarios": [huge_label],
        "Arcs": [
            {
                "name": huge_label,
                "summary": huge_body,
                "objective": huge_body,
                "scenarios": [huge_label],
            }
        ],
    }
    scenarios = [
        {
            "Title": huge_label,
            "Summary": huge_body,
            "Briefing": huge_body,
            "NPCs": [huge_label],
        }
    ]

    payload = build_campaign_graph_payload(campaign, scenarios)

    assert payload is not None
    assert len(payload.name) <= module.LABEL_DISPLAY_LIMIT
    assert payload.name.endswith("…")
    assert len(payload.logline) <= module.LONGFORM_DISPLAY_LIMIT
    assert payload.logline.endswith("…")
    assert len(payload.arcs[0].name) <= module.LABEL_DISPLAY_LIMIT
    assert len(payload.arcs[0].summary) <= module.LONGFORM_DISPLAY_LIMIT
    assert len(payload.arcs[0].scenarios[0].title) <= module.LABEL_DISPLAY_LIMIT
    assert len(payload.arcs[0].scenarios[0].summary) <= module.LONGFORM_DISPLAY_LIMIT
    assert len(payload.arcs[0].scenarios[0].entity_links[0].name) <= module.LABEL_DISPLAY_LIMIT
