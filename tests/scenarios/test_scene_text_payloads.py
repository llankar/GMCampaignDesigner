"""Tests for scene text payload normalization."""

from modules.scenarios.wizard_steps.scenes.scene_mode_adapters import canonicalise_scene
from modules.scenarios.wizard_steps.scenes.text_payloads import extract_plain_scene_text


def test_extract_plain_scene_text_parses_python_dict_string():
    payload = "{'text': 'Intro line\\nSecond line', 'formatting': {'bold': []}}"
    assert extract_plain_scene_text(payload) == "Intro line\nSecond line"


def test_extract_plain_scene_text_parses_json_dict_string():
    payload = '{"text":"Alpha beta","formatting":{"italic":[]}}'
    assert extract_plain_scene_text(payload) == "Alpha beta"


def test_canonicalise_scene_uses_plain_text_from_serialized_payload():
    scene = {
        "Title": "Scene 1",
        "Text": "{'text': 'Pilot jumps from the plane.', 'formatting': {'bold': []}}",
    }
    canonical = canonicalise_scene(scene)
    assert canonical["Summary"] == "Pilot jumps from the plane."
