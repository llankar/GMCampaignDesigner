import json

import pytest

from db import db as db_module
from db.db import get_campaign_setting
from modules.campaigns.services.ai.generation_defaults import (
    DEFAULT_AI_GENERATION_DEFAULTS,
    load_ai_generation_defaults,
    save_ai_generation_defaults,
)
from modules.helpers.config_helper import ConfigHelper


@pytest.fixture
def campaign_db(monkeypatch, tmp_path):
    db_path = tmp_path / "campaign.db"

    original_get = ConfigHelper.get

    def fake_get(cls, section, key, fallback=None):
        if (section, key) == ("Database", "path"):
            return str(db_path)
        if (section, key) == ("Logging", "enabled"):
            return "false"
        return original_get(section, key, fallback=fallback)

    monkeypatch.setattr(ConfigHelper, "get", classmethod(fake_get))
    ConfigHelper._config = None
    ConfigHelper._config_mtime = None

    db_module.initialize_db()
    return db_path


def test_ai_generation_defaults_save_and_load_round_trip(campaign_db):
    saved = save_ai_generation_defaults(
        {
            "main_pc_factions": ["Dawn Guard", "dawn guard"],
            "protected_factions": ["Free Cities"],
            "forbidden_antagonist_factions": ["Ash League"],
            "tone_hard_constraints": ["No cosmic horror", "no cosmic horror"],
            "allow_internal_conflict": True,
        }
    )

    assert saved == {
        "main_pc_factions": ["Dawn Guard"],
        "protected_factions": ["Free Cities"],
        "forbidden_antagonist_factions": ["Ash League"],
        "tone_hard_constraints": ["No cosmic horror"],
        "allow_internal_conflict": True,
    }

    stored = get_campaign_setting("ai_generation_defaults_json")
    assert json.loads(stored) == saved
    assert load_ai_generation_defaults() == saved


def test_ai_generation_defaults_invalid_json_falls_back_to_defaults(campaign_db):
    db_module.set_campaign_setting("ai_generation_defaults_json", "{invalid}")

    assert load_ai_generation_defaults() == DEFAULT_AI_GENERATION_DEFAULTS


def test_ai_generation_defaults_defaults_when_missing(campaign_db):
    assert load_ai_generation_defaults() == DEFAULT_AI_GENERATION_DEFAULTS
