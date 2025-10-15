"""Utilities for loading and caching campaign system configuration."""

from __future__ import annotations

import json
import logging
import os
import threading
from contextlib import closing
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Callable, List, Mapping, Optional, Sequence, Set, Tuple, Union

from db.db import (
    get_connection,
    get_selected_system_slug,
    set_selected_system_slug,
)
from modules.helpers.logging_helper import log_module_import

log_module_import(__name__)

logger = logging.getLogger(__name__)

FaceValue = Union[int, str]
ChangeCallback = Callable[["SystemConfig"], None]

_EMPTY_MAPPING: Mapping[str, Any] = MappingProxyType({})


@dataclass(frozen=True)
class AnalyzerPattern:
    """Normalized representation of an analyzer pattern entry."""

    name: str
    pattern: str
    description: Optional[str] = None
    metadata: Mapping[str, Any] = field(default_factory=lambda: _EMPTY_MAPPING)


@dataclass(frozen=True)
class SystemConfig:
    """Fully parsed system configuration for the active campaign."""

    slug: str
    label: str
    default_formula: Optional[str]
    supported_faces: Tuple[FaceValue, ...]
    analyzer_patterns: Tuple[AnalyzerPattern, ...]
    analyzer_config: Mapping[str, Any] = field(default_factory=lambda: _EMPTY_MAPPING)


class SystemConfigManager:
    """Loader and cache for campaign system configuration."""

    _lock = threading.RLock()
    _cached_config: Optional[SystemConfig] = None
    _cached_slug: Optional[str] = None
    _cached_signature: Optional[Tuple[Optional[str], Optional[float], Optional[int], Optional[int]]] = None
    _listeners: Set[ChangeCallback] = set()

    @classmethod
    def get_current_system_config(cls) -> Optional[SystemConfig]:
        """Return the cached system configuration, refreshing if required."""

        with cls._lock:
            config, changed = cls._refresh_cache(force=False)
        if changed and config is not None:
            cls._notify_listeners(config)
        return config

    @classmethod
    def refresh_current_system(cls) -> Optional[SystemConfig]:
        """Force a reload of the active system configuration."""

        with cls._lock:
            config, changed = cls._refresh_cache(force=True)
        if changed and config is not None:
            cls._notify_listeners(config)
        return config

    @classmethod
    def set_current_system(cls, slug: str) -> Optional[SystemConfig]:
        """Persist a new active system slug and refresh the cache."""

        normalized = (slug or "").strip()
        if not normalized:
            raise ValueError("System slug must be a non-empty string.")

        if not cls._system_exists(normalized):
            raise ValueError(f"Unknown campaign system slug: {normalized}")

        set_selected_system_slug(normalized)

        with cls._lock:
            # Force cache refresh since we know the selection just changed.
            config, changed = cls._refresh_cache(force=True)
            result = cls._cached_config

        if config is not None and changed:
            cls._notify_listeners(config)

        return result

    @classmethod
    def list_available_systems(cls) -> Tuple[SystemConfig, ...]:
        """Return all configured systems parsed into :class:`SystemConfig` objects."""

        rows = cls._fetch_all_system_rows()
        systems = tuple(cls._row_to_config(row) for row in rows if row)
        return systems

    @classmethod
    def register_change_listener(cls, callback: ChangeCallback) -> Callable[[], None]:
        """Register a callback invoked whenever the active system changes."""

        if not callable(callback):
            raise TypeError("callback must be callable")

        with cls._lock:
            cls._listeners.add(callback)

        def _unsubscribe() -> None:
            cls.unregister_change_listener(callback)

        return _unsubscribe

    @classmethod
    def unregister_change_listener(cls, callback: ChangeCallback) -> None:
        """Remove a previously registered change listener."""

        with cls._lock:
            cls._listeners.discard(callback)

    # Internal helpers -------------------------------------------------
    @classmethod
    def _refresh_cache(
        cls,
        *,
        force: bool,
    ) -> Tuple[Optional[SystemConfig], bool]:
        """Reload the cached configuration if required.

        Returns a tuple of (config, changed) indicating whether the cached
        configuration was updated.
        """

        current_slug = get_selected_system_slug()
        signature = cls._compute_db_signature()

        needs_reload = force
        if not needs_reload:
            needs_reload = (
                cls._cached_config is None
                or current_slug != cls._cached_slug
                or signature != cls._cached_signature
            )

        if not needs_reload:
            return cls._cached_config, False

        config = cls._resolve_system_config(current_slug)

        previous_config = cls._cached_config
        cls._cached_config = config
        cls._cached_slug = config.slug if config else None
        cls._cached_signature = signature

        changed = config != previous_config
        return config, changed

    @classmethod
    def _resolve_system_config(cls, slug: Optional[str]) -> Optional[SystemConfig]:
        """Load the system configuration for ``slug`` (falling back to defaults)."""

        if slug:
            config = cls._load_config_for_slug(slug)
            if config:
                return config
            logger.warning("Requested system slug '%s' not found, falling back to default.", slug)

        config = cls._load_first_system()
        if config and slug != config.slug:
            try:
                set_selected_system_slug(config.slug)
            except Exception:  # pragma: no cover - defensive logging
                logger.exception("Failed to persist fallback system slug '%s'.", config.slug)
            else:
                cls._cached_signature = cls._compute_db_signature()
        return config

    @classmethod
    def _load_config_for_slug(cls, slug: str) -> Optional[SystemConfig]:
        query = (
            "SELECT slug, label, default_formula, supported_faces_json, analyzer_config_json "
            "FROM campaign_systems WHERE slug = ?"
        )
        with closing(get_connection()) as conn:
            cursor = conn.execute(query, (slug,))
            row = cursor.fetchone()
        return cls._row_to_config(row) if row else None

    @classmethod
    def _load_first_system(cls) -> Optional[SystemConfig]:
        query = (
            "SELECT slug, label, default_formula, supported_faces_json, analyzer_config_json "
            "FROM campaign_systems ORDER BY slug LIMIT 1"
        )
        with closing(get_connection()) as conn:
            cursor = conn.execute(query)
            row = cursor.fetchone()
        return cls._row_to_config(row) if row else None

    @classmethod
    def _fetch_all_system_rows(cls) -> Sequence[Tuple[Any, ...]]:
        query = (
            "SELECT slug, label, default_formula, supported_faces_json, analyzer_config_json "
            "FROM campaign_systems ORDER BY label, slug"
        )
        with closing(get_connection()) as conn:
            cursor = conn.execute(query)
            rows = cursor.fetchall()
        return rows

    @classmethod
    def _row_to_config(cls, row: Optional[Sequence[Any]]) -> Optional[SystemConfig]:
        if not row:
            return None
        slug, label, default_formula, supported_faces_json, analyzer_config_json = row
        supported_faces = cls._parse_supported_faces(supported_faces_json)
        patterns, analyzer_config = cls._parse_analyzer_config(analyzer_config_json)
        cleaned_formula = default_formula.strip() if isinstance(default_formula, str) else None
        if cleaned_formula == "":
            cleaned_formula = None
        return SystemConfig(
            slug=str(slug),
            label=str(label),
            default_formula=cleaned_formula,
            supported_faces=supported_faces,
            analyzer_patterns=patterns,
            analyzer_config=analyzer_config,
        )

    @staticmethod
    def _parse_supported_faces(raw_json: Optional[str]) -> Tuple[FaceValue, ...]:
        if not raw_json:
            return tuple()
        try:
            parsed = json.loads(raw_json)
        except json.JSONDecodeError:
            logger.warning("Invalid supported_faces_json encountered: %s", raw_json)
            return tuple()

        if isinstance(parsed, list):
            faces: List[FaceValue] = []
            for face in parsed:
                if isinstance(face, (int, str)):
                    faces.append(face)
            return tuple(faces)
        if isinstance(parsed, (int, str)):
            return (parsed,)
        return tuple()

    @classmethod
    def _parse_analyzer_config(
        cls, raw_json: Optional[str]
    ) -> Tuple[Tuple[AnalyzerPattern, ...], Mapping[str, Any]]:
        if not raw_json:
            return tuple(), _EMPTY_MAPPING

        try:
            parsed = json.loads(raw_json)
        except json.JSONDecodeError:
            logger.warning("Invalid analyzer_config_json encountered; ignoring")
            return tuple(), _EMPTY_MAPPING

        if isinstance(parsed, dict):
            config_dict = parsed
        elif isinstance(parsed, list):
            config_dict = {"patterns": parsed}
        else:
            return tuple(), _EMPTY_MAPPING

        patterns_source = config_dict.get("patterns", [])
        patterns: List[AnalyzerPattern] = []
        if isinstance(patterns_source, list):
            for index, entry in enumerate(patterns_source):
                if not isinstance(entry, dict):
                    continue
                name = entry.get("name") or entry.get("label") or f"pattern_{index}"
                pattern_value = entry.get("pattern") or entry.get("regex")
                if not isinstance(pattern_value, str) or not pattern_value:
                    continue
                description = entry.get("description")
                extras = {
                    key: value
                    for key, value in entry.items()
                    if key not in {"name", "label", "pattern", "regex", "description"}
                }
                patterns.append(
                    AnalyzerPattern(
                        name=str(name),
                        pattern=pattern_value,
                        description=str(description) if isinstance(description, str) else None,
                        metadata=cls._mapping_proxy(extras),
                    )
                )

        return tuple(patterns), cls._mapping_proxy(config_dict)

    @staticmethod
    def _mapping_proxy(data: Optional[Mapping[str, Any]]) -> Mapping[str, Any]:
        if not data:
            return _EMPTY_MAPPING
        try:
            return MappingProxyType(dict(data))
        except TypeError:
            # ``data`` might not be a mapping (e.g. list) - normalize to empty mapping.
            return _EMPTY_MAPPING

    @classmethod
    def _system_exists(cls, slug: str) -> bool:
        query = "SELECT 1 FROM campaign_systems WHERE slug = ?"
        with closing(get_connection()) as conn:
            cursor = conn.execute(query, (slug,))
            return cursor.fetchone() is not None

    @classmethod
    def _compute_db_signature(cls) -> Tuple[Optional[str], Optional[float], Optional[int], Optional[int]]:
        db_path: Optional[str] = None
        schema_version: Optional[int] = None
        user_version: Optional[int] = None
        with closing(get_connection()) as conn:
            cursor = conn.execute("PRAGMA database_list")
            for row in cursor.fetchall():
                if len(row) >= 3 and row[1] == "main":
                    db_path = row[2]
                    break
            cursor = conn.execute("PRAGMA schema_version")
            row = cursor.fetchone()
            if row:
                schema_version = row[0]
            cursor = conn.execute("PRAGMA user_version")
            row = cursor.fetchone()
            if row:
                user_version = row[0]

        mtime: Optional[float] = None
        if db_path and os.path.exists(db_path):
            try:
                mtime = os.path.getmtime(db_path)
            except OSError:
                mtime = None

        return db_path, mtime, schema_version, user_version

    @classmethod
    def _notify_listeners(cls, config: SystemConfig) -> None:
        # Copy listeners to avoid holding the lock while invoking callbacks.
        with cls._lock:
            listeners = tuple(cls._listeners)
        for callback in listeners:
            try:
                callback(config)
            except Exception:  # pragma: no cover - do not break on listener errors
                logger.exception("System change listener failed")


def get_current_system_config() -> Optional[SystemConfig]:
    """Public shortcut for :meth:`SystemConfigManager.get_current_system_config`."""

    return SystemConfigManager.get_current_system_config()


def refresh_current_system() -> Optional[SystemConfig]:
    """Public shortcut for :meth:`SystemConfigManager.refresh_current_system`."""

    return SystemConfigManager.refresh_current_system()


def set_current_system(slug: str) -> Optional[SystemConfig]:
    """Public shortcut for :meth:`SystemConfigManager.set_current_system`."""

    return SystemConfigManager.set_current_system(slug)


def list_available_systems() -> Tuple[SystemConfig, ...]:
    """Public shortcut for :meth:`SystemConfigManager.list_available_systems`."""

    return SystemConfigManager.list_available_systems()


def register_system_change_listener(callback: ChangeCallback) -> Callable[[], None]:
    """Register a listener for system configuration changes."""

    return SystemConfigManager.register_change_listener(callback)


def unregister_system_change_listener(callback: ChangeCallback) -> None:
    """Unregister a previously registered listener."""

    SystemConfigManager.unregister_change_listener(callback)


__all__ = [
    "AnalyzerPattern",
    "SystemConfig",
    "get_current_system_config",
    "refresh_current_system",
    "set_current_system",
    "list_available_systems",
    "register_system_change_listener",
    "unregister_system_change_listener",
    "SystemConfigManager",
]
