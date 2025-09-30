import pytest

from db.db import ensure_entity_schema
from modules.generic.generic_model_wrapper import GenericModelWrapper
from modules.helpers.config_helper import ConfigHelper


@pytest.fixture()
def temp_db(monkeypatch, tmp_path):
    db_path = tmp_path / "campaign.db"

    def fake_get(cls, section, key, fallback=None):
        if section == "Database" and key == "path":
            return str(db_path)
        return fallback

    monkeypatch.setattr(ConfigHelper, "get", classmethod(fake_get))

    # Ensure a fresh schema for the scenarios table inside the temporary DB.
    ensure_entity_schema("scenarios")

    return GenericModelWrapper("scenarios")


def test_upsert_item_preserves_other_rows(temp_db):
    wrapper = temp_db

    wrapper.save_items(
        [
            {"Title": "Adventure 1", "Summary": "Alpha"},
            {"Title": "Adventure 2", "Summary": "Beta"},
        ]
    )

    wrapper.upsert_item({"Title": "Adventure 1", "Summary": "Updated"})

    items = {item["Title"]: item for item in wrapper.load_items()}

    assert len(items) == 2
    assert items["Adventure 1"]["Summary"] == "Updated"
    assert "Adventure 2" in items
