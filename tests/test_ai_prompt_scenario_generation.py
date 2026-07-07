"""Tests for AI prompt library and scenario generation helpers."""


import pytest

from modules.scenarios.ai_prompt_library import (
    PromptLibrary,
    PromptLibraryError,
    PromptQuestion,
    ScenarioPrompt,
    extract_placeholders,
    validate_prompt,
)
from modules.scenarios.ai_scenario_generator import build_final_prompt, parse_generated_scenario, validate_required_answers


def test_extract_placeholders_ignores_duplicates_and_invalid_format_parts():
    assert extract_placeholders("Use {theme} in {location}. Again {theme} and {npc.name}.") == ["theme", "location", "npc"]


def test_validate_prompt_requires_name_text_and_unique_names():
    prompt = ScenarioPrompt.new("", "", "", "", [])
    existing = [ScenarioPrompt.new("Existing", "", "", "Text", [])]
    duplicate = ScenarioPrompt.new("Existing", "", "", "Text", [])
    errors = validate_prompt(prompt, existing)
    assert "Prompt name is required." in errors
    assert "Prompt text is required." in errors
    assert validate_prompt(duplicate, existing) == ["A prompt named 'Existing' already exists."]


def test_prompt_library_load_save_import_export_roundtrip(tmp_path):
    library = PromptLibrary(tmp_path / "prompts.json")
    prompt = ScenarioPrompt.new("Mystery", "Desc", "Modern", "Write {theme}", [PromptQuestion("theme", "Theme")])
    library.save([prompt])
    loaded = library.load()
    assert loaded[0].name == "Mystery"
    exported = tmp_path / "export.json"
    library.export_to_file(loaded, exported)
    imported_library = PromptLibrary(tmp_path / "imported.json")
    imported = imported_library.import_from_file(exported, merge=False)
    assert imported[0].questions[0].key == "theme"


def test_prompt_library_rejects_invalid_json_import(tmp_path):
    library = PromptLibrary(tmp_path / "prompts.json")
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    with pytest.raises(PromptLibraryError):
        library.import_from_file(bad)


def test_build_final_prompt_and_required_answers():
    prompt = ScenarioPrompt.new(
        "Prompt",
        "",
        "",
        "Type {scenario_type}; theme {theme}; unknown {unknown}",
        [PromptQuestion("scenario_type", "Type"), PromptQuestion("theme", "Theme")],
    )
    assert validate_required_answers(prompt, {"scenario_type": "fantasy"}) == ["Theme"]
    final, unresolved = build_final_prompt(prompt, {"scenario_type": "fantasy", "theme": "betrayal"})
    assert "Type fantasy" in final
    assert unresolved == ["unknown"]


def test_parse_generated_scenario_sections_best_effort():
    text = """Title: The Ash Bell
Scenario Summary, maximum 8 short lines:
A bell wakes the dead.
Secrets and Twists:
The priest is the bell.
NPCs:
- Mara, ash-smudged smith
Locations:
- The cracked belfry
"""
    parsed = parse_generated_scenario(text)
    assert parsed["Title"] == "The Ash Bell"
    assert parsed["Secrets"] == "The priest is the bell."
    assert parsed["NPCs"] == ["Mara, ash-smudged smith"]
    assert parsed["Places"] == ["The cracked belfry"]
