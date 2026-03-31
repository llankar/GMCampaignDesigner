"""Regression tests for date agenda validation."""

from datetime import date

from modules.events.services.date_validation import validate_iso_text


def test_validate_iso_text_supports_distant_lower_date():
    """Verify that validate iso text supports distant lower date."""
    result = validate_iso_text("1212-11-05")
    assert result.is_valid is True
    assert result.date_value == date(1212, 11, 5)


def test_validate_iso_text_supports_distant_upper_date():
    """Verify that validate iso text supports distant upper date."""
    result = validate_iso_text("2077-12-31")
    assert result.is_valid is True
    assert result.date_value == date(2077, 12, 31)


def test_validate_iso_text_rejects_non_leap_february_29():
    """Verify that validate iso text rejects non leap february 29."""
    result = validate_iso_text("2023-02-29")
    assert result.is_valid is False
    assert "Jour invalide" in (result.error_message or "")


def test_validate_iso_text_rejects_month_13():
    """Verify that validate iso text rejects month 13."""
    result = validate_iso_text("2023-13-10")
    assert result.is_valid is False
    assert result.error_message == "Mois invalide (1-12)."


def test_validate_iso_text_rejects_day_zero():
    """Verify that validate iso text rejects day zero."""
    result = validate_iso_text("2023-01-00")
    assert result.is_valid is False
    assert "Jour invalide" in (result.error_message or "")
