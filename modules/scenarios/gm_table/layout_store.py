"""Persistence for GM Table layouts."""

from __future__ import annotations

import json
import os
from typing import Any

from modules.scenarios.gm_table.table_registry import get_table_name, normalize_table_id

from modules.helpers.config_helper import ConfigHelper
from modules.helpers.logging_helper import log_info, log_warning


class GMTableLayoutStore:
    """Persist GM Table workspace state per campaign and table id."""

    FILE_NAME = "gm_table_layouts.json"

    def __init__(self) -> None:
        self.path = os.path.join(ConfigHelper.get_campaign_dir(), self.FILE_NAME)
        self.data: dict[str, Any] = {"tables": {}, "global": {}}
        self._read()

    def _read(self) -> None:
        """Load persisted data if present."""
        if not os.path.exists(self.path):
            return
        try:
            with open(self.path, "r", encoding="utf-8") as handle:
                loaded = json.load(handle)
            if isinstance(loaded, dict):
                # Current schema is table-first: {"tables": {}, "global": {}}.
                # Keep legacy scenario data in memory when present so older callers can
                # still read or migrate it without binding new table saves to scenario titles.
                tables = loaded.get("tables")
                global_settings = loaded.get("global")
                scenarios = loaded.get("scenarios")
                if isinstance(tables, dict) or isinstance(global_settings, dict):
                    self.data["tables"] = dict(tables or {})
                    self.data["global"] = dict(global_settings or {})
                    if isinstance(scenarios, dict):
                        self.data["scenarios"] = dict(scenarios)
                    return

                # Very old files were a bare mapping of scenario title to layout.
                self.data["scenarios"] = dict(loaded)
        except Exception as exc:
            log_warning(
                f"Unable to load GM Table layouts: {exc}",
                func_name="GMTableLayoutStore._read",
            )

    def _write(self) -> None:
        """Persist data to disk."""
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        tmp_path = f"{self.path}.tmp"
        with open(tmp_path, "w", encoding="utf-8") as handle:
            json.dump(self.data, handle, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, self.path)
        log_info(
            f"GM Table layouts saved to {self.path}",
            func_name="GMTableLayoutStore._write",
        )

    @staticmethod
    def _deep_copy(payload: Any) -> Any:
        """Return a deep copy that is safe to mutate."""
        return json.loads(json.dumps(payload))

    def get_table_layout(self, table_id: str) -> dict[str, Any]:
        """Return the saved layout for a stable table id."""
        normalized_id = normalize_table_id(table_id)
        layout = self.data.get("tables", {}).get(normalized_id) or {}
        if not isinstance(layout, dict):
            return {}
        return self._deep_copy(layout)

    def save_table_layout(self, table_id: str, layout: dict[str, Any]) -> None:
        """Persist a layout for a stable table id."""
        normalized_id = normalize_table_id(table_id)
        self.data.setdefault("tables", {})[normalized_id] = self._deep_copy(layout or {})
        self._write()

    def clear_table_layout(self, table_id: str) -> None:
        """Delete the layout for a stable table id."""
        normalized_id = normalize_table_id(table_id)
        tables = self.data.setdefault("tables", {})
        if normalized_id in tables:
            tables.pop(normalized_id, None)
            self._write()

    def get_table_name(self, table_id: str) -> str:
        """Return a custom table name or the registered default for ``table_id``."""
        normalized_id = normalize_table_id(table_id)
        names = self.data.setdefault("global", {}).setdefault("table_names", {})
        custom_name = names.get(normalized_id) if isinstance(names, dict) else None
        if isinstance(custom_name, str) and custom_name.strip():
            return custom_name.strip()
        return get_table_name(normalized_id)

    def save_table_name(self, table_id: str, name: str) -> None:
        """Persist a custom display name for a stable table id."""
        normalized_id = normalize_table_id(table_id)
        cleaned_name = str(name or "").strip()
        names = self.data.setdefault("global", {}).setdefault("table_names", {})
        if not isinstance(names, dict):
            names = {}
            self.data.setdefault("global", {})["table_names"] = names
        default_name = get_table_name(normalized_id)
        if cleaned_name and cleaned_name != default_name:
            names[normalized_id] = cleaned_name
        else:
            names.pop(normalized_id, None)
        self._write()

    def clear_table_name(self, table_id: str) -> None:
        """Remove a custom display name so the table falls back to its default."""
        normalized_id = normalize_table_id(table_id)
        names = self.data.setdefault("global", {}).setdefault("table_names", {})
        if isinstance(names, dict) and normalized_id in names:
            names.pop(normalized_id, None)
            self._write()

    def get_global_setting(self, key: str, default: Any = None) -> Any:
        """Return a global GM Table setting."""
        return self._deep_copy(self.data.get("global", {}).get(key, default))

    def set_global_setting(self, key: str, value: Any) -> None:
        """Persist a global GM Table setting."""
        self.data.setdefault("global", {})[key] = self._deep_copy(value)
        self._write()
