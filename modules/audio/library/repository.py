"""Repository helpers for library."""

from __future__ import annotations

import copy
import json
import os
import uuid
from typing import Any, Dict, Iterable, List, Optional

from modules.audio.services.music_mood_classifier import NO_MOOD
from modules.helpers.logging_helper import log_error, log_warning


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


def default_state() -> Dict[str, Dict[str, Any]]:
    """Handle default state."""
    return {
        "music": {
            "categories": {},
            "settings": {
                "volume": 0.65,
                "shuffle": False,
                "loop": True,
                "continue": True,
                "last_directory": "",
                "last_category": "",
                "last_mood": "",
                "last_track_id": "",
            },
        },
        "effects": {
            "categories": {},
            "settings": {
                "volume": 0.75,
                "shuffle": False,
                "loop": False,
                "continue": True,
                "last_directory": "",
                "last_category": "",
                "last_mood": "",
                "last_track_id": "",
            },
        },
    }


class AudioLibraryRepository:
    def __init__(self, path: str = "config/audio_library.json") -> None:
        """Initialize the AudioLibraryRepository instance."""
        self.path = path

    def load(self) -> Dict[str, Dict[str, Any]]:
        """Load the operation."""
        if not os.path.exists(self.path):
            state = default_state()
            self.save(state)
            return state

        try:
            # Keep load resilient if this step fails.
            with open(self.path, "r", encoding="utf-8") as handle:
                raw = json.load(handle)
        except Exception as exc:  # pragma: no cover - defensive
            log_warning(f"AudioLibraryRepository.load - failed to read {self.path}: {exc}")
            state = default_state()
            self.save(state)
            return state

        if not isinstance(raw, dict):
            raw = {}

        state, changed = self._merge_with_defaults(raw)
        if changed:
            self.save(state)
        return state

    def save(self, data: Dict[str, Dict[str, Any]]) -> None:
        """Save the operation."""
        directory = os.path.dirname(self.path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        try:
            # Keep save resilient if this step fails.
            with open(self.path, "w", encoding="utf-8") as handle:
                json.dump(data, handle, indent=2, ensure_ascii=False)
        except Exception as exc:  # pragma: no cover
            log_error(f"AudioLibraryRepository.save - failed to write {self.path}: {exc}")

    def compatibility_category_view(self, data: Dict[str, Dict[str, Any]], section: str, category: str) -> Dict[str, Any]:
        """Handle compatibility category view."""
        payload = self._get_category(data, section, category)
        tracks: List[Dict[str, Any]] = []
        moods = payload.get("moods", {})
        if isinstance(moods, dict):
            for mood_name, bucket in moods.items():
                # Process each (mood_name, bucket) from moods.items().
                if not isinstance(bucket, dict):
                    continue
                bucket_tracks = bucket.get("tracks", [])
                if not isinstance(bucket_tracks, list):
                    continue
                for track in bucket_tracks:
                    if isinstance(track, dict):
                        tracks.append(dict(track))
        tracks.sort(key=lambda item: str(item.get("name", "")).lower())
        return {
            "directories": list(payload.get("directories", [])),
            "moods": copy.deepcopy(moods),
            "tracks": tracks,
        }

    def _merge_with_defaults(self, raw: Dict[str, Any]) -> tuple[Dict[str, Dict[str, Any]], bool]:
        """Merge with defaults."""
        state = default_state()
        changed = False
        for section in ("music", "effects"):
            # Process each section from ('music', 'effects').
            section_raw = raw.get(section, {})
            if not isinstance(section_raw, dict):
                changed = True
                continue

            categories_raw = section_raw.get("categories", {})
            cleaned_categories: Dict[str, Dict[str, Any]] = {}
            if isinstance(categories_raw, dict):
                for name, payload in categories_raw.items():
                    # Process each (name, payload) from categories_raw.items().
                    if not isinstance(name, str):
                        changed = True
                        continue
                    cleaned, migrated = self._sanitize_category_payload(name, payload)
                    cleaned_categories[name] = cleaned
                    changed = changed or migrated
            else:
                changed = True

            settings_raw = section_raw.get("settings", {})
            if isinstance(settings_raw, dict):
                # Handle the branch where isinstance(settings_raw, dict).
                defaults = state[section]["settings"]
                for key in defaults:
                    if key in settings_raw:
                        defaults[key] = settings_raw[key]
            else:
                changed = True

            state[section]["categories"] = cleaned_categories
        return state, changed

    def _sanitize_category_payload(self, category: str, payload: Any) -> tuple[Dict[str, Any], bool]:
        """Internal helper for sanitize category payload."""
        if not isinstance(payload, dict):
            payload = {}
        migrated = False

        directories_raw = payload.get("directories", [])
        directories: List[str] = []
        if isinstance(directories_raw, list):
            for directory in directories_raw:
                if isinstance(directory, str) and directory:
                    directories.append(self.normalize_path(directory))
        else:
            migrated = True

        moods_payload = payload.get("moods")
        if isinstance(moods_payload, dict):
            # Handle the branch where isinstance(moods_payload, dict).
            moods: Dict[str, Dict[str, Any]] = {}
            seen_paths: set[str] = set()
            for mood_name, mood_data in moods_payload.items():
                mood_key = self.sanitize_mood(mood_name)
                mood_tracks_raw = mood_data.get("tracks", []) if isinstance(mood_data, dict) else []
                cleaned_tracks = self._sanitize_tracks_list(mood_tracks_raw, category, mood_key, seen_paths)
                moods[mood_key] = {"tracks": cleaned_tracks}
        else:
            moods = {}
            migrated = True

        legacy_tracks = payload.get("tracks", [])
        if isinstance(legacy_tracks, list) and legacy_tracks:
            # Continue with this path when isinstance(legacy_tracks, list) and legacy tracks is set.
            migrated = True
            seen_paths = {
                track.get("path")
                for bucket in moods.values()
                for track in bucket.get("tracks", [])
                if isinstance(track, dict)
            }
            for entry in legacy_tracks:
                # Process each entry from legacy_tracks.
                mood_key = self.sanitize_mood(entry.get("mood", NO_MOOD) if isinstance(entry, dict) else NO_MOOD)
                moods.setdefault(mood_key, {"tracks": []})
                sanitized = self.sanitize_track(entry, category=category, forced_mood=mood_key)
                if sanitized is None:
                    continue
                path_key = sanitized["path"]
                if path_key in seen_paths:
                    continue
                moods[mood_key]["tracks"].append(sanitized)
                seen_paths.add(path_key)

        for bucket in moods.values():
            bucket["tracks"].sort(key=lambda item: str(item.get("name", "")).lower())

        if not moods:
            moods = {NO_MOOD: {"tracks": []}}

        return {"directories": directories, "moods": moods}, migrated

    def _sanitize_tracks_list(
        self,
        tracks_raw: Any,
        category: str,
        mood: str,
        seen_paths: set[str],
    ) -> List[Dict[str, Any]]:
        """Internal helper for sanitize tracks list."""
        cleaned: List[Dict[str, Any]] = []
        if not isinstance(tracks_raw, list):
            return cleaned
        for entry in tracks_raw:
            # Process each entry from tracks_raw.
            sanitized = self.sanitize_track(entry, category=category, forced_mood=mood)
            if sanitized is None:
                continue
            path_key = sanitized["path"]
            if path_key in seen_paths:
                continue
            cleaned.append(sanitized)
            seen_paths.add(path_key)
        return cleaned

    def sanitize_track(
        self,
        data: Any,
        *,
        category: str,
        forced_mood: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Handle sanitize track."""
        if not isinstance(data, dict):
            return None
        path = data.get("path")
        if not isinstance(path, str) or not path.strip():
            return None
        normalized = self.normalize_path(path)
        name = data.get("name")
        if not isinstance(name, str) or not name.strip():
            name = os.path.splitext(os.path.basename(normalized))[0]
        track_id = data.get("id")
        if not isinstance(track_id, str) or not track_id.strip():
            track_id = uuid.uuid4().hex
        mood = forced_mood if forced_mood is not None else self.sanitize_mood(data.get("mood", NO_MOOD))
        return {
            "id": track_id,
            "name": name.strip(),
            "path": normalized,
            "category": category,
            "mood": mood,
        }

    def sanitize_mood(self, value: Any) -> str:
        """Handle sanitize mood."""
        if not isinstance(value, str):
            return NO_MOOD
        mood = value.strip().casefold()
        return mood or NO_MOOD

    def normalize_path(self, value: str) -> str:
        """Normalize path."""
        try:
            expanded = os.path.expanduser(value)
            absolute = os.path.abspath(expanded)
            return os.path.normpath(absolute)
        except Exception:  # pragma: no cover
            return value

    def get_category_payload(self, data: Dict[str, Dict[str, Any]], section: str, category: str) -> Dict[str, Any]:
        """Return category payload."""
        return self._get_category(data, section, category)

    def get_categories_payload(self, data: Dict[str, Dict[str, Any]], section: str) -> Dict[str, Dict[str, Any]]:
        """Return categories payload."""
        section_data = self._get_section(data, section)
        categories = section_data.setdefault("categories", {})
        return categories  # type: ignore[return-value]

    def _get_section(self, data: Dict[str, Dict[str, Any]], section: str) -> Dict[str, Any]:
        """Return section."""
        if section not in data:
            raise KeyError(f"Unknown section '{section}'.")
        return data[section]

    def _get_category(self, data: Dict[str, Dict[str, Any]], section: str, category: str) -> Dict[str, Any]:
        """Return category."""
        categories = self.get_categories_payload(data, section)
        if category not in categories:
            raise KeyError(f"Unknown category '{category}' in section '{section}'.")
        return categories[category]

    def collect_audio_files(self, directory: str, *, recursive: bool = True) -> List[str]:
        """Collect audio files."""
        collected: List[str] = []
        if not os.path.isdir(directory):
            return collected

        for root, _dirs, files in os.walk(directory):
            # Process each (root, _dirs, files) from os.walk(directory).
            for filename in files:
                # Process each filename from files.
                extension = os.path.splitext(filename)[1].lower()
                if extension in AUDIO_EXTENSIONS:
                    collected.append(os.path.join(root, filename))
            if not recursive:
                break
        collected.sort()
        return collected
