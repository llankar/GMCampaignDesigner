"""Persistence for recent image import roots (campaign-local settings)."""

from __future__ import annotations

import json
from typing import Callable

from db.db import get_campaign_setting, set_campaign_setting

from .root_selection import normalize_roots


_RECENT_ROOTS_SETTING_KEY = "image_import_recent_roots_json"
_DEFAULT_LIMIT = 12


class RecentImportRootsStore:
    """Load/save campaign-local recent roots for quick reuse."""

    def __init__(
        self,
        *,
        get_setting: Callable[[str, str | None], str | None] = get_campaign_setting,
        set_setting: Callable[[str, str | None], None] = set_campaign_setting,
        limit: int = _DEFAULT_LIMIT,
    ) -> None:
        self._get_setting = get_setting
        self._set_setting = set_setting
        self._limit = max(1, int(limit))

    def load(self) -> list[str]:
        """Return normalized recent roots from campaign settings."""
        raw = self._get_setting(_RECENT_ROOTS_SETTING_KEY, None)
        if not raw:
            return []
        try:
            parsed = json.loads(raw)
        except (TypeError, ValueError, json.JSONDecodeError):
            return []
        if not isinstance(parsed, list):
            return []
        return normalize_roots(parsed)[: self._limit]

    def save(self, roots: list[str]) -> None:
        """Persist normalized roots (most recent first)."""
        normalized = normalize_roots(roots)[: self._limit]
        payload = json.dumps(normalized, ensure_ascii=False)
        self._set_setting(_RECENT_ROOTS_SETTING_KEY, payload)
