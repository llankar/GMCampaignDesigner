"""Persistence for GM Table layouts."""

from __future__ import annotations

import json
import os
from typing import Any

from modules.helpers.config_helper import ConfigHelper
from modules.helpers.logging_helper import log_info, log_warning


class GMTableLayoutStore:
    """Persist GM Table workspace state per campaign and scenario."""

    FILE_NAME = "gm_table_layouts.json"

    def __init__(self) -> None:
        self.path = os.path.join(ConfigHelper.get_campaign_dir(), self.FILE_NAME)
        self.data: dict[str, Any] = {"scenarios": {}, "global": {}}
        self._read()

    def _read(self) -> None:
        """Load persisted data if present."""
        if not os.path.exists(self.path):
            return
        try:
            with open(self.path, "r", encoding="utf-8") as handle:
                loaded = json.load(handle)
            if isinstance(loaded, dict):
                self.data["scenarios"] = dict(loaded.get("scenarios") or {})
                self.data["global"] = dict(loaded.get("global") or {})
        except Exception as exc:
            log_warning(
                f"Unable to load GM Table layouts: {exc}",
                func_name="GMTableLayoutStore._read",
            )

    def _write(self) -> None:
        """Persist data to disk."""
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as handle:
            json.dump(self.data, handle, indent=2)
        log_info(
            f"GM Table layouts saved to {self.path}",
            func_name="GMTableLayoutStore._write",
        )

    @staticmethod
    def _deep_copy(payload: Any) -> Any:
        """Return a deep copy that is safe to mutate."""
        return json.loads(json.dumps(payload))

    def get_scenario_layout(self, scenario_title: str) -> dict[str, Any]:
        """Return the saved layout for a scenario."""
        if not scenario_title:
            return {}
        layout = self.data.get("scenarios", {}).get(scenario_title) or {}
        if not isinstance(layout, dict):
            return {}
        return self._deep_copy(layout)

    def save_scenario_layout(self, scenario_title: str, layout: dict[str, Any]) -> None:
        """Persist a scenario layout."""
        if not scenario_title:
            return
        self.data.setdefault("scenarios", {})[scenario_title] = self._deep_copy(layout or {})
        self._write()

    def clear_scenario_layout(self, scenario_title: str) -> None:
        """Delete a scenario layout."""
        if not scenario_title:
            return
        scenarios = self.data.setdefault("scenarios", {})
        if scenario_title in scenarios:
            scenarios.pop(scenario_title, None)
            self._write()

    def get_global_setting(self, key: str, default: Any = None) -> Any:
        """Return a global GM Table setting."""
        return self._deep_copy(self.data.get("global", {}).get(key, default))

    def set_global_setting(self, key: str, value: Any) -> None:
        """Persist a global GM Table setting."""
        self.data.setdefault("global", {})[key] = self._deep_copy(value)
        self._write()
