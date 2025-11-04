from contextlib import closing

import os
import sqlite3
import time

import pytest

from db import db as db_module
from modules.dice import dice_preferences
from modules.helpers.config_helper import ConfigHelper
from modules.helpers.system_config import SystemConfigManager, set_current_system


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


@pytest.mark.usefixtures("campaign_db")
def test_rollable_default_formula_uses_system_overrides():
    set_current_system("d20")
    assert dice_preferences.get_rollable_default_formula() == "1d20"

    set_current_system("2d20")
    assert dice_preferences.get_rollable_default_formula() == "2d20"

    set_current_system("savage_fate")
    assert dice_preferences.get_rollable_default_formula() == "1d6"


@pytest.mark.usefixtures("campaign_db")
def test_rollable_default_formula_ignores_configured_variants(campaign_db):
    with closing(sqlite3.connect(str(campaign_db))) as conn:
        conn.execute(
            "UPDATE campaign_systems SET default_formula = ? WHERE slug = ?",
            ("1dF + 1d6", "savage_fate"),
        )
        conn.commit()

    os.utime(campaign_db, None)
    time.sleep(0.01)

    set_current_system("savage_fate")

    assert dice_preferences.get_rollable_default_formula() == "1d6"


@pytest.mark.usefixtures("campaign_db")
def test_default_roll_options_respect_system_config(campaign_db):
    set_current_system("d20")
    options = dice_preferences.get_default_roll_options()
    assert options["separate"] is False
    assert options["explode"] is False

    set_current_system("2d20")
    options = dice_preferences.get_default_roll_options()
    assert options["separate"] is True
    assert options["explode"] is False

    set_current_system("savage_fate")
    options = dice_preferences.get_default_roll_options()
    assert options["separate"] is True
    assert options["explode"] is True
