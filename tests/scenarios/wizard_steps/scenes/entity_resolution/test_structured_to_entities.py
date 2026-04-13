"""Tests for structured -> entities resolver."""

from modules.scenarios.wizard_steps.scenes.entity_resolution.structured_to_entities import (
    build_campaign_entity_indexes,
    normalize_name,
    resolve_entities_from_structured,
)


class _Wrapper:
    def __init__(self, items):
        self._items = items

    def load_items(self):
        return list(self._items)


def _entity_wrappers():
    return {
        "npcs": _Wrapper([{"Name": "Katarzyna Ręzycka"}, {"Name": "Captain Mira"}, {"Name": "Katarzyna"}]),
        "creatures": _Wrapper([{"Name": "Ghoul"}, {"Name": "Stone Golem"}]),
        "places": _Wrapper([{"Name": "Królewska Wieża"}]),
        "clues": _Wrapper([{"Name": "Journal de Ręka"}]),
    }


def test_normalize_name_removes_diacritics_and_light_punctuation():
    assert normalize_name("  Ręzycka, Katarzyna!  ") == "rezycka katarzyna"


def test_partial_subset_match_from_structured_npc_line():
    indexes = build_campaign_entity_indexes(_entity_wrappers())
    scene = {"SceneNPCs": ["Dyrektorka Katarzyna Ręzycka"]}

    resolved = resolve_entities_from_structured(scene, indexes)

    assert resolved["NPCs"] == ["Katarzyna Ręzycka"]


def test_fuzzy_single_token_typo_distance_one_matches_when_unique():
    indexes = build_campaign_entity_indexes(_entity_wrappers())
    scene = {"SceneNPCs": ["Katazyna"]}

    resolved = resolve_entities_from_structured(scene, indexes)

    assert resolved["NPCs"] == ["Katarzyna"]


def test_diacritics_match_across_places_and_clues():
    indexes = build_campaign_entity_indexes(_entity_wrappers())
    scene = {
        "SceneLocations": ["Krolewska Wieza"],
        "SceneClues": ["Journal de Reka"],
    }

    resolved = resolve_entities_from_structured(scene, indexes)

    assert resolved["Places"] == ["Królewska Wieża"]
    assert resolved["Clues"] == ["Journal de Ręka"]


def test_generic_obstacle_lines_do_not_create_false_positives():
    indexes = build_campaign_entity_indexes(_entity_wrappers())
    scene = {
        "SceneObstacles": [
            "gardien de sécurité",
            "drones autonomes",
        ]
    }

    resolved = resolve_entities_from_structured(scene, indexes)

    assert resolved == {"NPCs": [], "Creatures": [], "Places": [], "Clues": []}
