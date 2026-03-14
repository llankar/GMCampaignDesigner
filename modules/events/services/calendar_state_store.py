from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from modules.helpers.config_helper import ConfigHelper
from modules.events.services.campaign_date_service import CampaignDateService


class CalendarStateStore:
    """Persist and restore calendar UI state in a campaign-local JSON file."""

    DEFAULT_STATE = {
        "view_mode": "month",
        "active_date": None,
        "filters": {
            "show_source": True,
            "search_text": "",
            "type": "",
            "entity": "",
            "status": "",
            "agenda_window_days": 7,
        },
        "panel_widths": {
            "left_sidebar": None,
            "center_grid": None,
        },
    }

    def __init__(self, file_path: str | Path | None = None):
        default_path = Path(ConfigHelper.get_campaign_dir()) / "calendar_state.json"
        self._file_path = Path(file_path) if file_path else default_path

    def load(self):
        state = self._default_copy()
        if not self._file_path.exists():
            return state

        try:
            payload = json.loads(self._file_path.read_text(encoding="utf-8"))
        except Exception:
            return state

        if not isinstance(payload, dict):
            return state

        return self._sanitize_state(payload)

    def save(self, state):
        if not isinstance(state, dict):
            return

        sanitized = self._sanitize_state(state)
        self._file_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self._file_path.write_text(json.dumps(sanitized, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            return

    def _sanitize_state(self, payload):
        state = self._default_copy()

        view_mode = str(payload.get("view_mode") or "").strip().lower()
        if view_mode:
            state["view_mode"] = view_mode

        parsed_date = self._parse_date(payload.get("active_date"))
        if parsed_date is not None:
            state["active_date"] = parsed_date.isoformat()

        filters_payload = payload.get("filters")
        if isinstance(filters_payload, dict):
            state["filters"]["show_source"] = bool(filters_payload.get("show_source", True))
            state["filters"]["search_text"] = str(filters_payload.get("search_text") or "").strip()
            state["filters"]["type"] = str(filters_payload.get("type") or "").strip()
            state["filters"]["entity"] = str(filters_payload.get("entity") or "").strip()
            state["filters"]["status"] = str(filters_payload.get("status") or "").strip()
            agenda_days = self._int_or_none(filters_payload.get("agenda_window_days"))
            if agenda_days in (7, 30):
                state["filters"]["agenda_window_days"] = agenda_days

        panel_payload = payload.get("panel_widths")
        if isinstance(panel_payload, dict):
            for key in state["panel_widths"]:
                width = self._int_or_none(panel_payload.get(key))
                if width is not None and width >= 0:
                    state["panel_widths"][key] = width

        return state

    @classmethod
    def to_runtime_state(cls, stored_state):
        state = cls()._sanitize_state(stored_state or {})
        runtime = {
            "view_mode": state["view_mode"],
            "active_date": cls._parse_date(state.get("active_date")) or CampaignDateService.get_today(),
            "filters": dict(state["filters"]),
            "panel_widths": dict(state["panel_widths"]),
        }
        return runtime

    @staticmethod
    def _parse_date(value):
        if isinstance(value, date):
            return value
        if not value:
            return None
        try:
            return date.fromisoformat(str(value))
        except Exception:
            return None

    @staticmethod
    def _int_or_none(value):
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @classmethod
    def _default_copy(cls):
        return {
            "view_mode": cls.DEFAULT_STATE["view_mode"],
            "active_date": cls.DEFAULT_STATE["active_date"],
            "filters": dict(cls.DEFAULT_STATE["filters"]),
            "panel_widths": dict(cls.DEFAULT_STATE["panel_widths"]),
        }

