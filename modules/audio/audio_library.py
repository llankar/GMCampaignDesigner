import json
import os
import uuid
from typing import Any, Dict, Iterable, List, Optional

from modules.helpers.logging_helper import log_info, log_warning, log_error, log_module_import

log_module_import(__name__)

AUDIO_EXTENSIONS: set[str] = {
    ".mp3",
    ".wav",
    ".ogg",
    ".oga",
    ".flac",
    ".aac",
    ".m4a",
    ".opus",
    ".webm",
}


def _default_state() -> Dict[str, Dict[str, Any]]:
    return {
        "music": {
            "categories": {},
            "settings": {
                "volume": 0.65,
                "shuffle": False,
                "loop": True,
                "last_directory": "",
            },
        },
        "effects": {
            "categories": {},
            "settings": {
                "volume": 0.75,
                "shuffle": False,
                "loop": False,
                "last_directory": "",
            },
        },
    }

class AudioLibrary:
    """Persisted catalog of music and sound effects grouped by types."""

    def __init__(self, path: str = "config/audio_library.json") -> None:
        self.path = path
        self.data: Dict[str, Dict[str, Any]] = _default_state()
        self.load()

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------
    def load(self) -> None:
        if not os.path.exists(self.path):
            self._ensure_directory()
            self.save()
            return

        try:
            with open(self.path, "r", encoding="utf-8") as handle:
                raw = json.load(handle)
        except Exception as exc:  # pragma: no cover - defensive
            log_warning(
                f"AudioLibrary.load - failed to read {self.path}: {exc}",
                func_name="AudioLibrary.load",
            )
            self.data = _default_state()
            self.save()
            return

        if not isinstance(raw, dict):
            log_warning(
                f"AudioLibrary.load - unexpected structure in {self.path}",
                func_name="AudioLibrary.load",
            )
            raw = {}

        self.data = self._merge_with_defaults(raw)

    def save(self) -> None:
        self._ensure_directory()
        try:
            with open(self.path, "w", encoding="utf-8") as handle:
                json.dump(self.data, handle, indent=2, ensure_ascii=False)
        except Exception as exc:  # pragma: no cover - filesystem failure
            log_error(
                f"AudioLibrary.save - failed to write {self.path}: {exc}",
                func_name="AudioLibrary.save",
            )

    def _ensure_directory(self) -> None:
        directory = os.path.dirname(self.path)
        if directory:
            os.makedirs(directory, exist_ok=True)
    # ------------------------------------------------------------------
    # Structure sanitizing
    # ------------------------------------------------------------------
    def _merge_with_defaults(self, raw: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        state = _default_state()
        for section in ("music", "effects"):
            section_raw = raw.get(section, {})
            if not isinstance(section_raw, dict):
                continue

            categories_raw = section_raw.get("categories", {})
            cleaned_categories: Dict[str, Dict[str, Any]] = {}
            if isinstance(categories_raw, dict):
                for name, payload in categories_raw.items():
                    if not isinstance(name, str):
                        continue
                    if not isinstance(payload, dict):
                        payload = {}

                    tracks_list = payload.get("tracks", [])
                    directories_list = payload.get("directories", [])

                    tracks: List[Dict[str, Any]] = []
                    seen_paths: set[str] = set()
                    if isinstance(tracks_list, list):
                        for entry in tracks_list:
                            sanitized = self._sanitize_track(entry, category=name)
                            if sanitized is None:
                                continue
                            path_key = sanitized["path"]
                            if path_key in seen_paths:
                                continue
                            tracks.append(sanitized)
                            seen_paths.add(path_key)

                    directories: List[str] = []
                    if isinstance(directories_list, list):
                        for directory in directories_list:
                            if isinstance(directory, str) and directory:
                                directories.append(self._normalize_path(directory))

                    tracks.sort(key=lambda item: item["name"].lower())
                    cleaned_categories[name] = {
                        "tracks": tracks,
                        "directories": directories,
                    }

            state[section]["categories"] = cleaned_categories

            settings_raw = section_raw.get("settings", {})
            if isinstance(settings_raw, dict):
                section_settings = state[section]["settings"]
                for key in ("volume", "shuffle", "loop", "last_directory"):
                    if key in settings_raw:
                        section_settings[key] = settings_raw[key]

        return state

    def _sanitize_track(self, data: Any, *, category: str) -> Optional[Dict[str, Any]]:
        if not isinstance(data, dict):
            return None
        path = data.get("path")
        if not isinstance(path, str) or not path.strip():
            return None
        normalized = self._normalize_path(path)
        name = data.get("name")
        if not isinstance(name, str) or not name.strip():
            name = os.path.splitext(os.path.basename(normalized))[0]
        track_id = data.get("id")
        if not isinstance(track_id, str) or not track_id.strip():
            track_id = uuid.uuid4().hex
        return {
            "id": track_id,
            "name": name.strip(),
            "path": normalized,
            "category": category,
        }

    def _normalize_path(self, value: str) -> str:
        try:
            expanded = os.path.expanduser(value)
            absolute = os.path.abspath(expanded)
            return os.path.normpath(absolute)
        except Exception:  # pragma: no cover - defensive
            return value
    # ------------------------------------------------------------------
    # Category operations
    # ------------------------------------------------------------------
    def get_categories(self, section: str) -> List[str]:
        categories = list(self._get_categories_dict(section).keys())
        categories.sort(key=str.lower)
        return categories

    def add_category(self, section: str, name: str) -> None:
        name = name.strip()
        if not name:
            raise ValueError("Category name cannot be empty.")
        categories = self._get_categories_dict(section)
        if name in categories:
            raise ValueError(f"Category '{name}' already exists.")
        categories[name] = {"tracks": [], "directories": []}
        self.save()
        log_info(
            f"AudioLibrary.add_category - added '{name}' to {section}",
            func_name="AudioLibrary.add_category",
        )

    def remove_category(self, section: str, name: str) -> None:
        categories = self._get_categories_dict(section)
        if name not in categories:
            raise KeyError(f"Unknown category '{name}'.")
        del categories[name]
        self.save()
        log_info(
            f"AudioLibrary.remove_category - removed '{name}' from {section}",
            func_name="AudioLibrary.remove_category",
        )

    def rename_category(self, section: str, old_name: str, new_name: str) -> None:
        new_name = new_name.strip()
        categories = self._get_categories_dict(section)
        if old_name not in categories:
            raise KeyError(f"Unknown category '{old_name}'.")
        if not new_name:
            raise ValueError("New category name cannot be empty.")
        if new_name == old_name:
            return
        if new_name in categories:
            raise ValueError(f"Category '{new_name}' already exists.")

        payload = categories.pop(old_name)
        for track in payload.get("tracks", []):
            track["category"] = new_name
        categories[new_name] = payload
        self.save()
        log_info(
            f"AudioLibrary.rename_category - '{old_name}' -> '{new_name}' ({section})",
            func_name="AudioLibrary.rename_category",
        )

    def get_directories(self, section: str, category: str) -> List[str]:
        payload = self._get_category(section, category)
        return list(payload.get("directories", []))

    def add_directory(self, section: str, category: str, directory: str, *, recursive: bool = True) -> List[Dict[str, Any]]:
        normalized = self._normalize_path(directory)
        if not os.path.isdir(normalized):
            raise ValueError(f"Directory '{directory}' does not exist.")

        payload = self._get_category(section, category)
        directories: List[str] = payload.setdefault("directories", [])
        if normalized not in directories:
            directories.append(normalized)
            directories.sort(key=str.lower)

        discovered = self._collect_audio_files(normalized, recursive=recursive)
        added = self.add_tracks(section, category, discovered)
        if not added:
            self.save()
        return added

    def rescan_category(self, section: str, category: str) -> Dict[str, List[Dict[str, Any]]]:
        payload = self._get_category(section, category)
        existing_tracks: List[Dict[str, Any]] = payload.get("tracks", [])
        directories = payload.get("directories", [])

        removed: List[Dict[str, Any]] = []
        for track in list(existing_tracks):
            if not os.path.exists(track["path"]):
                existing_tracks.remove(track)
                removed.append(track)

        discovered_paths: List[str] = []
        for directory in directories:
            discovered_paths.extend(self._collect_audio_files(directory, recursive=True))

        added = self.add_tracks(section, category, discovered_paths)
        if removed and not added:
            self.save()

        return {"added": added, "removed": removed}
    # ------------------------------------------------------------------
    # Track level operations
    # ------------------------------------------------------------------
    def list_tracks(self, section: str, category: str) -> List[Dict[str, Any]]:
        payload = self._get_category(section, category)
        return list(payload.get("tracks", []))

    def add_tracks(self, section: str, category: str, paths: Iterable[str]) -> List[Dict[str, Any]]:
        payload = self._get_category(section, category)
        tracks: List[Dict[str, Any]] = payload.setdefault("tracks", [])
        existing_paths = {track["path"] for track in tracks}

        added: List[Dict[str, Any]] = []
        for raw_path in paths:
            normalized = self._normalize_path(raw_path)
            extension = os.path.splitext(normalized)[1].lower()
            if extension not in AUDIO_EXTENSIONS:
                continue
            if normalized in existing_paths:
                continue
            if not os.path.exists(normalized):
                log_warning(
                    f"AudioLibrary.add_tracks - missing file '{normalized}'",
                    func_name="AudioLibrary.add_tracks",
                )
                continue

            track = {
                "id": uuid.uuid4().hex,
                "name": os.path.splitext(os.path.basename(normalized))[0],
                "path": normalized,
                "category": category,
            }
            tracks.append(track)
            added.append(track)
            existing_paths.add(normalized)

        if added:
            tracks.sort(key=lambda item: item["name"].lower())
            self.save()
            log_info(
                f"AudioLibrary.add_tracks - added {len(added)} tracks to {section}/{category}",
                func_name="AudioLibrary.add_tracks",
            )
        return added

    def remove_track(self, section: str, category: str, track_id: str) -> Optional[Dict[str, Any]]:
        payload = self._get_category(section, category)
        tracks: List[Dict[str, Any]] = payload.get("tracks", [])
        for index, track in enumerate(tracks):
            if track.get("id") == track_id:
                removed = tracks.pop(index)
                self.save()
                log_info(
                    f"AudioLibrary.remove_track - removed '{removed['name']}'",
                    func_name="AudioLibrary.remove_track",
                )
                return removed
        return None
    # ------------------------------------------------------------------
    # Settings
    # ------------------------------------------------------------------
    def get_setting(self, section: str, key: str, default: Any = None) -> Any:
        section_data = self._get_section(section)
        return section_data.get("settings", {}).get(key, default)

    def set_setting(self, section: str, key: str, value: Any) -> None:
        section_data = self._get_section(section)
        section_data.setdefault("settings", {})[key] = value
        self.save()

    # ------------------------------------------------------------------
    # Internal lookup helpers
    # ------------------------------------------------------------------
    def _get_section(self, section: str) -> Dict[str, Any]:
        if section not in self.data:
            raise KeyError(f"Unknown section '{section}'.")
        return self.data[section]

    def _get_categories_dict(self, section: str) -> Dict[str, Dict[str, Any]]:
        section_data = self._get_section(section)
        categories = section_data.setdefault("categories", {})
        return categories  # type: ignore[return-value]

    def _get_category(self, section: str, category: str) -> Dict[str, Any]:
        categories = self._get_categories_dict(section)
        if category not in categories:
            raise KeyError(f"Unknown category '{category}' in section '{section}'.")
        return categories[category]

    def _collect_audio_files(self, directory: str, *, recursive: bool = True) -> List[str]:
        collected: List[str] = []
        if not os.path.isdir(directory):
            return collected

        for root, _dirs, files in os.walk(directory):
            for filename in files:
                extension = os.path.splitext(filename)[1].lower()
                if extension in AUDIO_EXTENSIONS:
                    collected.append(os.path.join(root, filename))
            if not recursive:
                break
        collected.sort()
        return collected
