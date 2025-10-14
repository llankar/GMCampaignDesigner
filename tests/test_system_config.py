import json
import os
import re
import sqlite3
import time
from contextlib import closing

import pytest

from db import db as db_module
from modules.helpers.config_helper import ConfigHelper
from modules.helpers.system_config import (
    SystemConfigManager,
    get_current_system_config,
    list_available_systems,
    register_system_change_listener,
    set_current_system,
)


def _reset_manager_state() -> None:
    SystemConfigManager._cached_config = None
    SystemConfigManager._cached_slug = None
    SystemConfigManager._cached_signature = None
    SystemConfigManager._listeners.clear()


@pytest.fixture
def campaign_db(monkeypatch, tmp_path):
    db_path = tmp_path / "campaign.db"

    original_get = ConfigHelper.get

    def fake_get(cls, section, key, fallback=None):
        if (section, key) == ("Database", "path"):
            return str(db_path)
        return original_get(section, key, fallback=fallback)

    monkeypatch.setattr(ConfigHelper, "get", classmethod(fake_get))

    db_module.initialize_db()
    _reset_manager_state()
    try:
        yield db_path
    finally:
        _reset_manager_state()


def test_system_config_seeds_defaults(campaign_db):
    config = get_current_system_config()
    assert config is not None
    assert config.slug == "d20"
    assert any(system.slug == "d20" for system in list_available_systems())


def test_system_config_switching_updates_selection_and_notifies(campaign_db):
    events = []

    unsubscribe = register_system_change_listener(lambda cfg: events.append(cfg.slug))
    try:
        initial = get_current_system_config()
        available = list_available_systems()
        target = next(system for system in available if system.slug != initial.slug)

        updated = set_current_system(target.slug)

        assert updated is not None
        assert updated.slug == target.slug
        assert get_current_system_config().slug == target.slug
        assert target.slug in events
    finally:
        unsubscribe()


def test_system_config_cache_invalidation_detects_db_changes(campaign_db):
    initial = get_current_system_config()
    assert initial is not None

    new_formula = "1d20+3"
    with closing(sqlite3.connect(str(campaign_db))) as conn:
        conn.execute(
            "UPDATE campaign_systems SET default_formula = ? WHERE slug = ?",
            (new_formula, initial.slug),
        )
        conn.commit()

    # Ensure the modification timestamp definitely changes for coarse filesystems.
    os.utime(campaign_db, None)
    time.sleep(0.01)

    refreshed = get_current_system_config()
    assert refreshed.default_formula == new_formula


def test_system_config_parses_analyzer_patterns(campaign_db):
    initial = get_current_system_config()
    assert initial is not None

    payload = {
        "attack_roll": {"base": "2d20", "template": "{base}{bonus}"},
        "difficulty_buttons": [
            {
                "label": "Standard Challenge",
                "template": "{attack_roll}",
                "descriptor": "Standard",
            }
        ],
        "patterns": [
            {
                "name": "2d20_stat_block",
                "pattern": r"(?P<label>\\w+)\\s+(?P<attack>[+-]\\d+)\\s+TN\\s+(?P<tn>\\d+)",
                "description": "2d20 inline stat block",
                "notes_group": "tn",
                "difficulties": [
                    {
                        "group": "tn",
                        "label": "Target Number",
                        "template": "{attack_roll}",
                        "descriptor": "TN",
                        "notes_group": "tn",
                    }
                ],
            }
        ],
    }

    with closing(sqlite3.connect(str(campaign_db))) as conn:
        conn.execute(
            "UPDATE campaign_systems SET analyzer_config_json = ? WHERE slug = ?",
            (json.dumps(payload), initial.slug),
        )
        conn.commit()

    os.utime(campaign_db, None)
    time.sleep(0.01)

    refreshed = get_current_system_config()
    assert refreshed is not None
    assert refreshed.analyzer_config["attack_roll"]["base"] == "2d20"

    assert refreshed.analyzer_patterns, "Expected analyzer patterns to be parsed"
    pattern = refreshed.analyzer_patterns[0]
    assert pattern.name == "2d20_stat_block"
    actual_pattern_text = re.compile(pattern.pattern).pattern
    expected_pattern_text = re.compile(payload["patterns"][0]["pattern"]).pattern
    assert actual_pattern_text == expected_pattern_text
    assert pattern.description == "2d20 inline stat block"
    assert pattern.metadata["notes_group"] == "tn"
    difficulties = pattern.metadata["difficulties"]
    assert isinstance(difficulties, list)
    assert difficulties[0]["label"] == "Target Number"
    assert difficulties[0]["template"] == "{attack_roll}"
    assert difficulties[0]["descriptor"] == "TN"

    default_buttons = refreshed.analyzer_config["difficulty_buttons"]
    assert isinstance(default_buttons, list)
    assert default_buttons[0]["label"] == "Standard Challenge"
    assert default_buttons[0]["template"] == "{attack_roll}"
