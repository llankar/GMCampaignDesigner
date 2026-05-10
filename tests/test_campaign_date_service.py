"""Regression tests for campaign date service."""

from datetime import date

import pytest

from db import db as db_module
from db.db import get_campaign_setting
from modules.events.services.campaign_date_service import CampaignDateService
from modules.events.services.calendar_state_store import CalendarStateStore
from modules.helpers.config_helper import ConfigHelper


@pytest.fixture
def campaign_db(monkeypatch, tmp_path):
    """Handle campaign DB."""
    db_path = tmp_path / "campaign.db"

    original_get = ConfigHelper.get

    def fake_get(cls, section, key, fallback=None):
        """Handle fake get."""
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


def test_campaign_date_service_persists_in_database(campaign_db):
    """Verify that campaign date service persists in database."""
    resolved = CampaignDateService.set_today("2026-07-14")

    assert resolved == date(2026, 7, 14)
    assert CampaignDateService.get_today() == date(2026, 7, 14)
    assert get_campaign_setting("timeline_current_date") == "2026-07-14"


def test_calendar_runtime_state_defaults_to_campaign_today(campaign_db):
    """Verify that calendar runtime state defaults to campaign today."""
    CampaignDateService.set_today("2030-01-02")

    runtime = CalendarStateStore.to_runtime_state({})

    assert runtime["active_date"] == date(2030, 1, 2)


def test_calendar_state_store_ignores_null_numeric_values(campaign_db):
    """Verify that nullable stored dimensions do not crash state restoration."""
    stored_state = {
        "filters": {"agenda_window_days": None},
        "panel_widths": {"left_sidebar": None, "center_grid": None},
    }

    runtime = CalendarStateStore.to_runtime_state(stored_state)

    assert runtime["filters"]["agenda_window_days"] == 7
    assert runtime["panel_widths"] == {"left_sidebar": None, "center_grid": None}


def test_campaign_date_service_rejects_invalid_values(campaign_db):
    """Verify that campaign date service rejects invalid values."""
    with pytest.raises(ValueError):
        CampaignDateService.set_today("not-a-date")
