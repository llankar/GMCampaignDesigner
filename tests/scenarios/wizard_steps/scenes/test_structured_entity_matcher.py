"""Tests for structured scene entity resolution."""

from modules.scenarios.wizard_steps.scenes.entity_resolution.structured_entity_matcher import (
    resolve_scene_entities_from_structured,
)


def _db_indexes():
    return {
        "NPCs": {
            "exact": {"Captain Mira": "Captain Mira", "Wolf": "Wolf"},
            "normalised": {"captain mira": "Captain Mira", "wolf": "Wolf"},
        },
        "Creatures": {
            "exact": {"Goblin": "Goblin", "Wolf": "Wolf"},
            "normalised": {"goblin": "Goblin", "wolf": "Wolf"},
        },
        "Places": {
            "exact": {"Old Mill": "Old Mill"},
            "normalised": {"old mill": "Old Mill"},
        },
        "Clues": {
            "exact": {"Broken Seal": "Broken Seal"},
            "normalised": {"broken seal": "Broken Seal"},
        },
    }


def test_match_exact():
    scene = {"SceneNPCs": ["Captain Mira"]}
    resolved = resolve_scene_entities_from_structured(scene, _db_indexes())
    assert resolved["NPCs"] == ["Captain Mira"]


def test_match_case_insensitive():
    scene = {"SceneLocations": ["old mill"]}
    resolved = resolve_scene_entities_from_structured(scene, _db_indexes())
    assert resolved["Places"] == ["Old Mill"]


def test_non_match_adds_nothing():
    scene = {"SceneObstacles": ["Unknown Thing"]}
    resolved = resolve_scene_entities_from_structured(scene, _db_indexes())
    assert resolved == {"NPCs": [], "Creatures": [], "Places": [], "Clues": []}


def test_dedupes_across_multiple_sections():
    scene = {
        "SceneNPCs": ["Captain Mira"],
        "SceneObstacles": ["Captain Mira", "Goblin"],
    }
    resolved = resolve_scene_entities_from_structured(scene, _db_indexes())
    assert resolved["NPCs"] == ["Captain Mira"]
    assert resolved["Creatures"] == ["Goblin"]


def test_section_priority_for_ambiguous_names():
    scene = {"SceneObstacles": ["Wolf"], "SceneClues": ["wolf"]}
    resolved = resolve_scene_entities_from_structured(scene, _db_indexes())
    assert resolved["Creatures"] == ["Wolf"]
    assert resolved["NPCs"] == []
    assert resolved["Clues"] == []

