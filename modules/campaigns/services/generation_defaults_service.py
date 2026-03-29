from __future__ import annotations

import json
from typing import Callable

from db.db import get_campaign_setting, set_campaign_setting
from modules.campaigns.services.generation_defaults_mapper import (
    DEFAULT_GENERATION_DEFAULTS_STATE,
    generation_defaults_payload_to_state,
    generation_defaults_state_to_payload,
)

CAMPAIGN_GENERATION_DEFAULTS_KEY = "campaign_generation_defaults"


class CampaignGenerationDefaultsService:
    """Load/save campaign-level AI generation defaults in campaign_settings."""

    def __init__(
        self,
        *,
        get_setting: Callable[[str, str | None], str | None] = get_campaign_setting,
        set_setting: Callable[[str, str | None], None] = set_campaign_setting,
    ):
        self._get_setting = get_setting
        self._set_setting = set_setting

    def load(self) -> dict:
        raw = self._get_setting(CAMPAIGN_GENERATION_DEFAULTS_KEY, None)
        if not raw:
            return dict(DEFAULT_GENERATION_DEFAULTS_STATE)
        try:
            parsed = json.loads(raw)
        except (TypeError, ValueError):
            return dict(DEFAULT_GENERATION_DEFAULTS_STATE)
        return generation_defaults_payload_to_state(parsed if isinstance(parsed, dict) else {})

    def save(self, state: dict | None) -> dict:
        payload = generation_defaults_state_to_payload(state)
        self._set_setting(CAMPAIGN_GENERATION_DEFAULTS_KEY, json.dumps(payload, ensure_ascii=False))
        return payload
