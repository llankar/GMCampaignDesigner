"""Regression tests for event schedule widgets."""

from datetime import date

from modules.events.ui.shared.schedule_widgets import (
    format_event_date,
    normalize_event_time,
    parse_event_date,
)


def test_parse_event_date_accepts_iso_and_day_first_formats():
    """Verify that parse event date accepts iso and day first formats."""
    assert parse_event_date("2026-03-10") == date(2026, 3, 10)
    assert parse_event_date("10/03/2026") == date(2026, 3, 10)
    assert parse_event_date("10-03-2026") == date(2026, 3, 10)


def test_format_event_date_normalizes_to_iso():
    """Verify that format event date normalizes to iso."""
    assert format_event_date("10/03/2026") == "2026-03-10"
    assert format_event_date(date(2026, 3, 10)) == "2026-03-10"


def test_normalize_event_time_accepts_common_shortcuts():
    """Verify that normalize event time accepts common shortcuts."""
    assert normalize_event_time("9") == "09:00"
    assert normalize_event_time("930") == "09:30"
    assert normalize_event_time("9h45") == "09:45"
    assert normalize_event_time("18.05") == "18:05"


def test_normalize_event_time_preserves_unknown_invalid_values():
    """Verify that normalize event time preserves unknown invalid values."""
    assert normalize_event_time("") == ""
    assert normalize_event_time("25:00") == "25:00"
    assert normalize_event_time("noon-ish") == "noon-ish"
