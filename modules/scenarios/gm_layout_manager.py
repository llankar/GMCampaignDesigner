import json
import os
from typing import Dict, Any, Optional

from modules.helpers.config_helper import ConfigHelper
from modules.helpers.logging_helper import log_info, log_warning, log_exception, log_module_import


class GMScreenLayoutManager:
    """Persist GM Screen tab layouts per campaign."""

    FILE_NAME = "gm_layouts.json"

    def __init__(self):
        self.path = os.path.join(ConfigHelper.get_campaign_dir(), self.FILE_NAME)
        self.data: Dict[str, Any] = {
            "layouts": {},
            "scenario_defaults": {},
            "scenario_state": {},
            "session_settings": {},
        }
        self._load()

    # ------------------------------------------------------------------
    # Basic persistence helpers
    # ------------------------------------------------------------------
    def _load(self) -> None:
        if not os.path.exists(self.path):
            log_info(f"No layout file found at {self.path}; starting fresh.", func_name="GMScreenLayoutManager._load")
            return
        try:
            with open(self.path, "r", encoding="utf-8") as fh:
                raw = json.load(fh) or {}
            layouts = raw.get("layouts") or {}
            scenario_defaults = raw.get("scenario_defaults") or {}
            scenario_state = raw.get("scenario_state") or {}
            session_settings = raw.get("session_settings") or {}
            if (
                not isinstance(layouts, dict)
                or not isinstance(scenario_defaults, dict)
                or not isinstance(scenario_state, dict)
                or not isinstance(session_settings, dict)
            ):
                raise ValueError("Layout file malformed")
            self.data["layouts"] = layouts
            self.data["scenario_defaults"] = scenario_defaults
            self.data["scenario_state"] = scenario_state
            self.data["session_settings"] = session_settings
        except Exception as exc:
            log_exception(exc, func_name="GMScreenLayoutManager._load")
            log_warning(
                f"Failed to load GM layouts from {self.path}. Reinitializing empty store.",
                func_name="GMScreenLayoutManager._load",
            )
            self.data = {
                "layouts": {},
                "scenario_defaults": {},
                "scenario_state": {},
                "session_settings": {},
            }

    def _write(self) -> None:
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as fh:
            json.dump(self.data, fh, indent=2)
        log_info(
            f"GM layouts saved to {self.path}",
            func_name="GMScreenLayoutManager._write",
        )

    # ------------------------------------------------------------------
    # Layout operations
    # ------------------------------------------------------------------
    def list_layouts(self) -> Dict[str, Any]:
        return dict(self.data.get("layouts", {}))

    def get_layout(self, name: str) -> Optional[Dict[str, Any]]:
        layouts = self.data.get("layouts", {})
        layout = layouts.get(name)
        if layout is None:
            return None
        return json.loads(json.dumps(layout))  # deep copy to avoid accidental mutation

    def save_layout(self, name: str, layout: Dict[str, Any]) -> None:
        self.data.setdefault("layouts", {})[name] = layout
        self._write()

    # ------------------------------------------------------------------
    # Scenario defaults
    # ------------------------------------------------------------------
    def get_scenario_default(self, scenario_title: str) -> Optional[str]:
        if not scenario_title:
            return None
        return self.data.get("scenario_defaults", {}).get(scenario_title)

    def set_scenario_default(self, scenario_title: str, layout_name: Optional[str]) -> None:
        defaults = self.data.setdefault("scenario_defaults", {})
        if not scenario_title:
            return
        if layout_name:
            defaults[scenario_title] = layout_name
        else:
            defaults.pop(scenario_title, None)
        self._write()

    # ------------------------------------------------------------------
    # Scenario state (notes, scene completion)
    # ------------------------------------------------------------------
    def get_scenario_state(self, scenario_title: str) -> Dict[str, Any]:
        if not scenario_title:
            return {}
        state = self.data.get("scenario_state", {}).get(scenario_title)
        if state is None:
            return {}
        return json.loads(json.dumps(state))

    def get_scene_view_mode(self, scenario_title: str) -> Optional[str]:
        state = self.get_scenario_state(scenario_title)
        mode = state.get("scene_view_mode")
        if mode in {"List", "Scene Flow"}:
            return mode
        return None

    def update_scenario_state(
        self,
        scenario_title: str,
        *,
        scenes: Optional[Dict[str, Any]] = None,
        notes: Optional[str] = None,
        scene_view_mode: Optional[str] = None,
    ) -> None:
        if not scenario_title:
            return
        store = self.data.setdefault("scenario_state", {})
        entry: Dict[str, Any] = store.setdefault(scenario_title, {})

        if scenes is not None:
            normalized = {key: bool(value) for key, value in (scenes or {}).items() if bool(value)}
            if normalized:
                entry["scenes"] = normalized
            else:
                entry.pop("scenes", None)

        if notes is not None:
            if notes:
                entry["notes"] = notes
            else:
                entry.pop("notes", None)

        if scene_view_mode is not None:
            if scene_view_mode in {"List", "Scene Flow"}:
                entry["scene_view_mode"] = scene_view_mode
            else:
                entry.pop("scene_view_mode", None)

        if not entry:
            store.pop(scenario_title, None)

        self._write()

    def set_scene_view_mode(self, scenario_title: str, mode: Optional[str]) -> None:
        normalized_mode = mode if mode in {"List", "Scene Flow"} else None
        self.update_scenario_state(scenario_title, scene_view_mode=normalized_mode)

    # ------------------------------------------------------------------
    # Session settings (plot twist scheduler hours)
    # ------------------------------------------------------------------
    def get_session_hours(self, scenario_title: str) -> Dict[str, float]:
        if not scenario_title:
            return {}
        raw = self.data.get("session_settings", {}).get(scenario_title) or {}
        if not isinstance(raw, dict):
            return {}
        return json.loads(json.dumps(raw))

    def set_session_hours(self, scenario_title: str, mid_hours: Optional[float], end_hours: Optional[float]) -> None:
        if not scenario_title:
            return
        store = self.data.setdefault("session_settings", {})
        if mid_hours is None and end_hours is None:
            store.pop(scenario_title, None)
        else:
            store[scenario_title] = {
                "mid_hours": mid_hours,
                "end_hours": end_hours,
            }
        self._write()


log_module_import(__name__)
