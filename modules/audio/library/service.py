from __future__ import annotations

import os
import uuid
from typing import Any, Dict, Iterable, List, Optional

from modules.audio.library.repository import AUDIO_EXTENSIONS, AudioLibraryRepository
from modules.audio.services.music_mood_classifier import NO_MOOD, classify_track_mood
from modules.helpers.logging_helper import log_info, log_warning


class AudioLibraryService:
    """Business API over the persisted audio library catalog."""

    def __init__(self, path: str = "config/audio_library.json", repository: Optional[AudioLibraryRepository] = None) -> None:
        self.repository = repository or AudioLibraryRepository(path)
        self.path = path
        self.data: Dict[str, Dict[str, Any]] = self.repository.load()

    def load(self) -> None:
        self.data = self.repository.load()

    def save(self) -> None:
        self.repository.save(self.data)

    def get_categories(self, section: str) -> List[str]:
        categories = list(self._get_categories_dict(section).keys())
        categories.sort(key=str.lower)
        return categories

    def get_moods(self, section: str, category: str) -> List[str]:
        payload = self._get_category(section, category)
        moods = list(payload.get("moods", {}).keys())
        moods.sort(key=str.lower)
        return moods

    def list_tracks(self, section: str, category: str, mood: Optional[str] = None) -> List[Dict[str, Any]]:
        payload = self._get_category(section, category)
        moods = payload.get("moods", {})
        if mood is not None:
            mood_key = self.repository.sanitize_mood(mood)
            bucket = moods.get(mood_key, {}) if isinstance(moods, dict) else {}
            tracks = list(bucket.get("tracks", [])) if isinstance(bucket, dict) else []
            tracks.sort(key=lambda item: str(item.get("name", "")).lower())
            return tracks

        merged: List[Dict[str, Any]] = []
        if isinstance(moods, dict):
            for bucket in moods.values():
                if isinstance(bucket, dict):
                    bucket_tracks = bucket.get("tracks", [])
                    if isinstance(bucket_tracks, list):
                        merged.extend(bucket_tracks)
        merged.sort(key=lambda item: str(item.get("name", "")).lower())
        return merged

    def add_mood(self, section: str, category: str, mood: str) -> None:
        mood_key = self.repository.sanitize_mood(mood)
        payload = self._get_category(section, category)
        moods = payload.setdefault("moods", {})
        if mood_key in moods:
            return
        moods[mood_key] = {"tracks": []}
        self.save()

    def rename_mood(self, section: str, category: str, old: str, new: str) -> None:
        old_key = self.repository.sanitize_mood(old)
        new_key = self.repository.sanitize_mood(new)
        payload = self._get_category(section, category)
        moods = payload.setdefault("moods", {})
        if old_key not in moods:
            raise KeyError(f"Unknown mood '{old}'.")
        if old_key == new_key:
            return
        if new_key in moods:
            raise ValueError(f"Mood '{new}' already exists.")
        bucket = moods.pop(old_key)
        tracks = bucket.get("tracks", []) if isinstance(bucket, dict) else []
        for track in tracks:
            if isinstance(track, dict):
                track["mood"] = new_key
        moods[new_key] = {"tracks": tracks}
        self.save()

    def remove_mood(self, section: str, category: str, mood: str) -> None:
        mood_key = self.repository.sanitize_mood(mood)
        payload = self._get_category(section, category)
        moods = payload.setdefault("moods", {})
        if mood_key not in moods:
            raise KeyError(f"Unknown mood '{mood}'.")
        del moods[mood_key]
        if not moods:
            moods[NO_MOOD] = {"tracks": []}
        self.save()

    # legacy compatibility helpers
    def get_moods_for_section(self, section: str) -> List[str]:
        moods: set[str] = set()
        for category in self.get_categories(section):
            moods.update(self.get_moods(section, category))
        return sorted(moods, key=str.lower)

    def list_tracks_by_mood(self, section: str, mood: str) -> List[Dict[str, Any]]:
        mood_key = self.repository.sanitize_mood(mood)
        items: List[Dict[str, Any]] = []
        for category in self.get_categories(section):
            items.extend(self.list_tracks(section, category, mood_key))
        items.sort(key=lambda item: str(item.get("name", "")).lower())
        return items

    def add_category(self, section: str, name: str) -> None:
        category = name.strip()
        if not category:
            raise ValueError("Category name cannot be empty.")
        categories = self._get_categories_dict(section)
        if category in categories:
            raise ValueError(f"Category '{category}' already exists.")
        categories[category] = {"directories": [], "moods": {NO_MOOD: {"tracks": []}}}
        self.save()

    def remove_category(self, section: str, name: str) -> None:
        categories = self._get_categories_dict(section)
        if name not in categories:
            raise KeyError(f"Unknown category '{name}'.")
        del categories[name]
        self.save()

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
        for mood in payload.get("moods", {}).values():
            for track in mood.get("tracks", []):
                track["category"] = new_name
        categories[new_name] = payload
        self.save()

    def get_directories(self, section: str, category: str) -> List[str]:
        payload = self._get_category(section, category)
        return list(payload.get("directories", []))

    def add_directory(
        self,
        section: str,
        category: str,
        mood: str,
        directory: str,
        *,
        recursive: bool = True,
    ) -> List[Dict[str, Any]]:
        normalized = self.repository.normalize_path(directory)
        if not os.path.isdir(normalized):
            raise ValueError(f"Directory '{directory}' does not exist.")

        payload = self._get_category(section, category)
        directories = payload.setdefault("directories", [])
        if normalized not in directories:
            directories.append(normalized)
            directories.sort(key=str.lower)

        discovered = self.repository.collect_audio_files(normalized, recursive=recursive)
        added = self.add_tracks(section, category, mood, discovered)
        if not added:
            self.save()
        return added

    def rescan_mood(self, section: str, category: str, mood: str) -> Dict[str, List[Dict[str, Any]]]:
        payload = self._get_category(section, category)
        mood_key = self.repository.sanitize_mood(mood)
        moods = payload.get("moods", {})
        bucket = moods.get(mood_key, {}) if isinstance(moods, dict) else {}
        tracks = bucket.get("tracks", []) if isinstance(bucket, dict) else []

        removed: List[Dict[str, Any]] = []
        for track in list(tracks):
            if not os.path.exists(track["path"]):
                tracks.remove(track)
                removed.append(track)

        discovered_paths: List[str] = []
        for directory in payload.get("directories", []):
            discovered_paths.extend(self.repository.collect_audio_files(directory, recursive=True))

        added = self.add_tracks(section, category, mood_key, discovered_paths)
        if removed and not added:
            self.save()

        return {"added": added, "removed": removed}

    def rescan_category(self, section: str, category: str) -> Dict[str, List[Dict[str, Any]]]:
        all_added: List[Dict[str, Any]] = []
        all_removed: List[Dict[str, Any]] = []
        for mood in self.get_moods(section, category):
            result = self.rescan_mood(section, category, mood)
            all_added.extend(result.get("added", []))
            all_removed.extend(result.get("removed", []))
        return {"added": all_added, "removed": all_removed}

    def add_tracks(
        self,
        section: str,
        category: str,
        mood: str,
        paths: Iterable[str],
    ) -> List[Dict[str, Any]]:
        payload = self._get_category(section, category)
        moods = payload.setdefault("moods", {})
        mood_key = self.repository.sanitize_mood(mood)
        target_bucket = moods.setdefault(mood_key, {"tracks": []})

        existing_paths = {
            track["path"]
            for mood in moods.values()
            for track in mood.get("tracks", [])
            if isinstance(track, dict) and isinstance(track.get("path"), str)
        }

        added: List[Dict[str, Any]] = []
        for raw_path in paths:
            normalized = self.repository.normalize_path(raw_path)
            extension = os.path.splitext(normalized)[1].lower()
            if extension not in AUDIO_EXTENSIONS:
                continue
            if normalized in existing_paths:
                continue
            if not os.path.exists(normalized):
                log_warning(f"AudioLibraryService.add_tracks - missing file '{normalized}'")
                continue

            track = {
                "id": uuid.uuid4().hex,
                "name": os.path.splitext(os.path.basename(normalized))[0],
                "path": normalized,
                "category": category,
                "mood": mood_key,
            }
            target_bucket.setdefault("tracks", []).append(track)
            added.append(track)
            existing_paths.add(normalized)

        if added:
            for bucket in moods.values():
                bucket["tracks"].sort(key=lambda item: item["name"].lower())
            self.save()
            log_info(
                f"AudioLibraryService.add_tracks - added {len(added)} tracks to {section}/{category}/{mood_key}"
            )
        return added

    def classify_section_moods(self, section: str) -> Dict[str, int]:
        categories = self._get_categories_dict(section)
        updated = 0
        for category_name, payload in categories.items():
            all_tracks = self.list_tracks(section, category_name)
            new_moods: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}
            for track in all_tracks:
                track_name = str(track.get("name", ""))
                mood = classify_track_mood(track_name)
                if track.get("mood") != mood:
                    updated += 1
                track["mood"] = mood
                track["category"] = category_name
                new_moods.setdefault(mood, {"tracks": []})["tracks"].append(track)
            for bucket in new_moods.values():
                bucket["tracks"].sort(key=lambda item: item["name"].lower())
            payload["moods"] = new_moods or {NO_MOOD: {"tracks": []}}
        if updated:
            self.save()
        return {"updated": updated}

    def remove_track(self, section: str, category: str, mood: str, track_id: str) -> Optional[Dict[str, Any]]:
        payload = self._get_category(section, category)
        mood_key = self.repository.sanitize_mood(mood)
        moods = payload.get("moods", {})
        bucket = moods.get(mood_key, {}) if isinstance(moods, dict) else {}
        tracks = bucket.get("tracks", []) if isinstance(bucket, dict) else []
        for index, track in enumerate(tracks):
            if track.get("id") == track_id:
                removed = tracks.pop(index)
                self.save()
                return removed
        return None

    def get_setting(self, section: str, key: str, default: Any = None) -> Any:
        section_data = self._get_section(section)
        return section_data.get("settings", {}).get(key, default)

    def set_setting(self, section: str, key: str, value: Any) -> None:
        section_data = self._get_section(section)
        section_data.setdefault("settings", {})[key] = value
        self.save()

    def get_compatibility_category(self, section: str, category: str) -> Dict[str, Any]:
        return self.repository.compatibility_category_view(self.data, section, category)

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
