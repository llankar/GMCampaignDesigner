"""Management helpers for scenario GM layout."""

import json
import os
from typing import Dict, Any, Optional

from modules.helpers.config_helper import ConfigHelper
from modules.helpers.logging_helper import log_info, log_warning, log_exception, log_module_import


class GMScreenLayoutManager:
    """Persist GM Screen tab layouts per campaign."""

    FILE_NAME = "gm_layouts.json"

    def __init__(self):
        """Initialize the GMScreenLayoutManager instance."""
        self.path = os.path.join(ConfigHelper.get_campaign_dir(), self.FILE_NAME)
        self.data: Dict[str, Any] = {
            "layouts": {},
            "scenario_defaults": {},
            "scenario_state": {},
            "session_settings": {},
            "global_settings": {},
            "layout_presets": {},
        }
        self._load()

    # ------------------------------------------------------------------
    # Basic persistence helpers
    # ------------------------------------------------------------------
    def _load(self) -> None:
        """Load the operation."""
        if not os.path.exists(self.path):
            log_info(f"No layout file found at {self.path}; starting fresh.", func_name="GMScreenLayoutManager._load")
            return
        try:
            # Keep load resilient if this step fails.
            with open(self.path, "r", encoding="utf-8") as fh:
                raw = json.load(fh) or {}
            layouts = raw.get("layouts") or {}
            scenario_defaults = raw.get("scenario_defaults") or {}
            scenario_state = raw.get("scenario_state") or {}
            session_settings = raw.get("session_settings") or {}
            global_settings = raw.get("global_settings") or {}
            layout_presets = raw.get("layout_presets") or {}
            if (
                not isinstance(layouts, dict)
                or not isinstance(scenario_defaults, dict)
                or not isinstance(scenario_state, dict)
                or not isinstance(session_settings, dict)
                or not isinstance(global_settings, dict)
                or not isinstance(layout_presets, dict)
            ):
                raise ValueError("Layout file malformed")
            self.data["layouts"] = layouts
            self.data["scenario_defaults"] = scenario_defaults
            self.data["scenario_state"] = scenario_state
            self.data["session_settings"] = session_settings
            self.data["global_settings"] = global_settings
            self.data["layout_presets"] = layout_presets
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
                "global_settings": {},
                "layout_presets": {},
            }

    def _write(self) -> None:
        """Internal helper for write."""
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
        """Handle list layouts."""
        return dict(self.data.get("layouts", {}))

    def get_layout(self, name: str) -> Optional[Dict[str, Any]]:
        """Return layout."""
        layouts = self.data.get("layouts", {})
        layout = layouts.get(name)
        if layout is None:
            return None
        return json.loads(json.dumps(layout))  # deep copy to avoid accidental mutation

    def save_layout(self, name: str, layout: Dict[str, Any]) -> None:
        """Save layout."""
        self.data.setdefault("layouts", {})[name] = layout
        self._write()

    # ------------------------------------------------------------------
    # Scenario defaults
    # ------------------------------------------------------------------
    def get_scenario_default(self, scenario_title: str) -> Optional[str]:
        """Return scenario default."""
        if not scenario_title:
            return None
        return self.data.get("scenario_defaults", {}).get(scenario_title)

    def set_scenario_default(self, scenario_title: str, layout_name: Optional[str]) -> None:
        """Set scenario default."""
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
        """Return scenario state."""
        if not scenario_title:
            return {}
        state = self.data.get("scenario_state", {}).get(scenario_title)
        if state is None:
            return {}
        return json.loads(json.dumps(state))

    def get_scene_view_mode(self, scenario_title: str) -> Optional[str]:
        """Return scene view mode."""
        state = self.get_scenario_state(scenario_title)
        mode = state.get("scene_view_mode")
        if mode in {"List", "Scene Flow"}:
            return mode
        return None

    def get_scene_list_density(self, scenario_title: str) -> Optional[str]:
        """Return scene list density."""
        state = self.get_scenario_state(scenario_title)
        density = state.get("scene_list_density")
        if density in {"Compact", "Normal", "Focus"}:
            return density
        return None

    def update_scenario_state(
        self,
        scenario_title: str,
        *,
        scenes: Optional[Dict[str, Any]] = None,
        notes: Optional[str] = None,
        scene_view_mode: Optional[str] = None,
        scene_list_density: Optional[str] = None,
    ) -> None:
        """Update scenario state."""
        if not scenario_title:
            return
        store = self.data.setdefault("scenario_state", {})
        entry: Dict[str, Any] = store.setdefault(scenario_title, {})

        if scenes is not None:
            # Handle the branch where scenes is available.
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

        if scene_list_density is not None:
            if scene_list_density in {"Compact", "Normal", "Focus"}:
                entry["scene_list_density"] = scene_list_density
            else:
                entry.pop("scene_list_density", None)

        if not entry:
            store.pop(scenario_title, None)

        self._write()

    def set_scene_view_mode(self, scenario_title: str, mode: Optional[str]) -> None:
        """Set scene view mode."""
        normalized_mode = mode if mode in {"List", "Scene Flow"} else None
        self.update_scenario_state(scenario_title, scene_view_mode=normalized_mode)

    # ------------------------------------------------------------------
    # Session settings (plot twist scheduler hours)
    # ------------------------------------------------------------------
    def get_session_hours(self, scenario_title: str) -> Dict[str, float]:
        """Return session hours."""
        if not scenario_title:
            return {}
        raw = self.data.get("session_settings", {}).get(scenario_title) or {}
        if not isinstance(raw, dict):
            return {}
        return json.loads(json.dumps(raw))

    def set_session_hours(self, scenario_title: str, mid_hours: Optional[float], end_hours: Optional[float]) -> None:
        """Set session hours."""
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



    # ------------------------------------------------------------------
    # Virtual desk layout presets
    # ------------------------------------------------------------------
    def list_layout_presets(self) -> Dict[str, Any]:
        """Return saved virtual desk presets."""
        return dict(self.data.get("layout_presets", {}))

    def get_layout_preset(self, name: str) -> Optional[Dict[str, Any]]:
        """Return a deep-copied layout preset by name."""
        if not name:
            return None
        presets = self.data.get("layout_presets", {})
        preset = presets.get(name)
        if preset is None:
            return None
        return json.loads(json.dumps(preset))

    def save_layout_preset(self, name: str, preset: Dict[str, Any]) -> None:
        """Persist a virtual desk preset."""
        if not name:
            return
        self.data.setdefault("layout_presets", {})[name] = preset
        self._write()

    def set_last_layout_preset(self, scenario_title: str, preset_name: Optional[str]) -> None:
        """Track the previously-applied preset per scenario."""
        if not scenario_title:
            return
        store = self.data.setdefault("scenario_state", {})
        entry: Dict[str, Any] = store.setdefault(scenario_title, {})
        if preset_name:
            entry["last_layout_preset"] = preset_name
        else:
            entry.pop("last_layout_preset", None)
        if not entry:
            store.pop(scenario_title, None)
        self._write()

    def get_last_layout_preset(self, scenario_title: str) -> Optional[str]:
        """Return the previous preset name stored for a scenario."""
        if not scenario_title:
            return None
        entry = self.data.get("scenario_state", {}).get(scenario_title) or {}
        value = entry.get("last_layout_preset")
        if isinstance(value, str) and value:
            return value
        return None

    # ------------------------------------------------------------------
    # Global settings
    # ------------------------------------------------------------------
    def get_global_setting(self, key: str, default: Any = None) -> Any:
        """Return a global setting value."""
        if not key:
            return default
        store = self.data.get("global_settings") or {}
        return store.get(key, default)

    def set_global_setting(self, key: str, value: Any) -> None:
        """Persist a global setting value."""
        if not key:
            return
        store = self.data.setdefault("global_settings", {})
        if value is None:
            store.pop(key, None)
        else:
            store[key] = value
        self._write()


log_module_import(__name__)
