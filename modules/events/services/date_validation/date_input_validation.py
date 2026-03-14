from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class DateAgendaValidationResult:
    date_value: date | None
    error_message: str | None
    max_day: int

    @property
    def is_valid(self) -> bool:
        return self.date_value is not None and self.error_message is None


def max_days_for_month(year: int, month: int) -> int:
    if not 1 <= int(month) <= 12:
        return 31
    safe_year = max(1, min(9999, int(year)))
    return calendar.monthrange(safe_year, int(month))[1]


def validate_date_parts(year: int, month: int, day: int) -> DateAgendaValidationResult:
    year_value = int(year)
    month_value = int(month)
    day_value = int(day)

    if not 1 <= year_value <= 9999:
        return DateAgendaValidationResult(None, "Année invalide (1-9999).", 31)
    if not 1 <= month_value <= 12:
        return DateAgendaValidationResult(None, "Mois invalide (1-12).", 31)

    max_day = max_days_for_month(year_value, month_value)
    if not 1 <= day_value <= max_day:
        return DateAgendaValidationResult(
            None,
            f"Jour invalide pour {year_value:04d}-{month_value:02d} (1-{max_day}).",
            max_day,
        )

    return DateAgendaValidationResult(date(year_value, month_value, day_value), None, max_day)


def validate_iso_text(raw_text: str) -> DateAgendaValidationResult:
    text = str(raw_text or "").strip()
    if not text:
        return DateAgendaValidationResult(None, "Saisissez une date au format YYYY-MM-DD.", 31)

    parts = text.split("-")
    if len(parts) != 3:
        return DateAgendaValidationResult(None, "Format invalide. Utilisez YYYY-MM-DD.", 31)

    try:
        year_value, month_value, day_value = (int(value) for value in parts)
    except ValueError:
        return DateAgendaValidationResult(None, "Format invalide. Utilisez YYYY-MM-DD.", 31)

    return validate_date_parts(year_value, month_value, day_value)
