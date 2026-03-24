from __future__ import annotations

import json
import zipfile

import campaign_generator
from modules.campaign_generator.services import (
    append_scenario_to_json_file,
    build_scenario_export_payload,
)


def _sample_campaign() -> dict[str, str]:
    return {
        "Starting Location": "Tavern – The party meets in a tavern.",
        "Quest": "Rescue Hostage – Save the missing diplomat.",
        "Quest Hook": "Duty – They owe a favor.",
        "Quest Giver": "Grizzled Captain – A veteran officer seeks assistance.",
        "Key NPC": "Witty Rogue – A sly contact knows the back alleys.",
        "Region": "Haunted Forest – A haunted forest with its own mysteries. Beyond it lies Ancient Ruins – danger waits.",
        "Travel Distance": "3 hexes – A trek of 3 hexes across wild lands.",
        "Random Encounter": "Bandit Ambush – Highwaymen strike from cover.",
        "Reward": "A rare artifact.",
        "Penalty": "A severe injury.",
        "Quest Item": "Ancient amulet.",
    }



def test_campaign_generator_facade_preserves_public_symbols():
    assert callable(campaign_generator.generate_fantasy_campaign)
    assert callable(campaign_generator.generate_scifi_campaign)
    assert callable(campaign_generator.generate_modern_campaign)
    assert callable(campaign_generator.generate_postapoc_campaign)
    assert callable(campaign_generator.export_to_docx)
    assert callable(campaign_generator.main)
    assert set(campaign_generator.GENERATOR_FUNCTIONS) == {
        "Fantasy",
        "Sci‑Fi",
        "Modern",
        "Post‑Apocalyptic",
    }



def test_build_scenario_export_payload_keeps_legacy_shape():
    payload = build_scenario_export_payload(_sample_campaign())

    assert payload["Title"] == "Rescue Hostage"
    assert payload["Summary"]["text"].startswith("Tavern")
    assert payload["Secrets"]["text"] == "A severe injury."
    assert payload["Places"][0] == "Tavern"
    assert payload["NPCs"] == ["Witty Rogue", "Grizzled Captain"]



def test_append_scenario_to_json_file_writes_scenarios_wrapper(tmp_path):
    output = tmp_path / "campaign.json"

    append_scenario_to_json_file(_sample_campaign(), str(output))
    append_scenario_to_json_file(_sample_campaign(), str(output))

    data = json.loads(output.read_text(encoding="utf-8"))
    assert list(data) == ["scenarios"]
    assert len(data["scenarios"]) == 2
    assert data["scenarios"][0]["Title"] == "Rescue Hostage"



def test_export_to_docx_creates_word_document(tmp_path):
    output = tmp_path / "campaign.docx"

    campaign_generator.export_to_docx(_sample_campaign(), str(output))

    assert output.exists()
    with zipfile.ZipFile(output) as archive:
        assert "[Content_Types].xml" in archive.namelist()
        document_xml = archive.read("word/document.xml").decode("utf-8")
    assert "Starting Location" in document_xml
    assert "Rescue Hostage" in document_xml
