"""Utilities for event campaign date service."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from db.db import get_campaign_setting, set_campaign_setting


_CAMPAIGN_DATE_KEY = "timeline_current_date"


class CampaignDateService:
    """Read and persist the campaign's reference "today" date in the DB."""

    @classmethod
    def get_today(cls) -> date:
        """Return today."""
        stored = get_campaign_setting(_CAMPAIGN_DATE_KEY)
        return cls.parse(stored) or date.today()

    @classmethod
    def set_today(cls, value: date | str) -> date:
        """Set today."""
        parsed = cls.parse(value)
        if parsed is None:
            raise ValueError("value must be a valid date")
        set_campaign_setting(_CAMPAIGN_DATE_KEY, parsed.isoformat())
        return parsed

    @staticmethod
    def parse(value: Any) -> date | None:
        """Parse the operation."""
        if isinstance(value, date):
            return value
        if value in (None, ""):
            return None

        text = str(value).strip()
        if not text:
            return None

        for candidate in (text, text[:10]):
            try:
                return date.fromisoformat(candidate)
            except ValueError:
                continue

        for fmt in ("%Y/%m/%d", "%d/%m/%Y"):
            try:
                return datetime.strptime(text, fmt).date()
            except ValueError:
                continue

        return None
