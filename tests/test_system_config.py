import os
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
