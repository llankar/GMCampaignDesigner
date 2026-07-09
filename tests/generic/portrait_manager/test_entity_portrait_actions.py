from pathlib import Path
from modules.generic.portrait_manager.entity_portrait_actions import (
    ScenarioPortraitEntity,
    extract_scenario_linked_entity_names,
    missing_portrait_indices,
    portrait_status,
    resolve_scenario_linked_entities,
)

class DummyWrapper:
    def __init__(self, entity_type, items=None):
        self.entity_type = entity_type
        self._items = items or []
    def _infer_key_field(self, key_field=None):
        return "Title" if self.entity_type == "books" else "Name"
    def load_items(self):
        return list(self._items)
    def save_item(self, item):
        self.saved = item

def test_extract_scenario_linked_entity_names_from_supported_fields():
    scenario = {
        "NPCs": ["Alice", {"Name": "Bob"}],
        "Places": "Town, Forest",
        "Books": [{"Title": "Codex"}],
        "NPCs": ["Alice", "Alice"],
    }
    assert extract_scenario_linked_entity_names(scenario) == [
        ("npcs", "Alice", "NPCs"),
        ("places", "Town", "Places"),
        ("places", "Forest", "Places"),
        ("books", "Codex", "Books"),
    ]

def test_resolve_scenario_linked_entities_uses_entity_wrapper_key_fields():
    data = {
        "npcs": [{"Name": "Alice"}],
        "books": [{"Title": "Codex"}],
    }
    def factory(entity_type):
        return DummyWrapper(entity_type, data.get(entity_type, []))
    entities = resolve_scenario_linked_entities({"NPCs": ["Alice"], "Books": ["Codex"]}, factory)
    assert [(entity.entity_type, entity.name, entity.record) for entity in entities] == [
        ("npcs", "Alice", {"Name": "Alice"}),
        ("books", "Codex", {"Title": "Codex"}),
    ]

def test_portrait_status_detection(tmp_path, monkeypatch):
    monkeypatch.setattr("modules.helpers.config_helper.ConfigHelper.get_campaign_dir", lambda: str(tmp_path))
    portrait = tmp_path / "assets" / "portraits" / "alice.png"
    portrait.parent.mkdir(parents=True)
    portrait.write_bytes(b"x")
    assert portrait_status({"Portrait": "assets/portraits/alice.png"}) == "Ready"
    assert portrait_status({"Portrait": "assets/portraits/missing.png"}) == "Missing file"
    assert portrait_status({"Portrait": ""}) == "Missing"

def test_missing_portrait_ordering(tmp_path, monkeypatch):
    monkeypatch.setattr("modules.helpers.config_helper.ConfigHelper.get_campaign_dir", lambda: str(tmp_path))
    portrait = tmp_path / "ok.png"
    portrait.write_bytes(b"x")
    wrapper = DummyWrapper("npcs")
    entities = [
        ScenarioPortraitEntity("npcs", "A", {"Name": "A", "Portrait": ""}, wrapper),
        ScenarioPortraitEntity("npcs", "B", {"Name": "B", "Portrait": str(portrait)}, wrapper),
        ScenarioPortraitEntity("npcs", "C", {"Name": "C", "Portrait": "missing.png"}, wrapper),
    ]
    assert missing_portrait_indices(entities) == [0, 2]
