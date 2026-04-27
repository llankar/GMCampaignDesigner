"""Campaign-local persistence helpers for Ambiance UI settings."""

from __future__ import annotations

import configparser
import json
from dataclasses import asdict, dataclass
from pathlib import Path

from modules.helpers.config_helper import ConfigHelper

_SECTION = "Ambiance"
_DEFAULT_DURATION_SEC = 8.0


@dataclass(slots=True)
class AmbianceSettings:
    """Serializable settings used by the Ambiance panel."""

    enabled: bool = False
    playlist_paths: tuple[str, ...] = ()
    default_duration_sec: float = _DEFAULT_DURATION_SEC
    transition: str = "fade"
    shuffle: bool = False
    loop: bool = True
    target_monitor_index: int = 1


def load_ambiance_settings() -> AmbianceSettings:
    """Load [Ambiance] settings from campaign-local settings.ini."""
    cfg = ConfigHelper.load_campaign_config()
    if not cfg.has_section(_SECTION):
        return AmbianceSettings()

    playlist_paths_raw = cfg.get(_SECTION, "playlist_paths", fallback="[]")
    playlist_paths = _parse_playlist_paths(playlist_paths_raw)

    return AmbianceSettings(
        enabled=_to_bool(cfg.get(_SECTION, "enabled", fallback=False), False),
        playlist_paths=playlist_paths,
        default_duration_sec=_to_float(
            cfg.get(_SECTION, "default_duration_sec", fallback=_DEFAULT_DURATION_SEC),
            _DEFAULT_DURATION_SEC,
        ),
        transition=(cfg.get(_SECTION, "transition", fallback="fade") or "fade").strip().lower(),
        shuffle=_to_bool(cfg.get(_SECTION, "shuffle", fallback=False), False),
        loop=_to_bool(cfg.get(_SECTION, "loop", fallback=True), True),
        target_monitor_index=_to_int(cfg.get(_SECTION, "target_monitor_index", fallback=1), 1),
    )


def save_ambiance_settings(settings: AmbianceSettings) -> None:
    """Persist settings in the campaign-local settings.ini file."""
    path = Path(ConfigHelper.get_campaign_settings_path())
    cfg = configparser.ConfigParser()
    if path.exists():
        cfg.read(path, encoding="utf-8")

    if not cfg.has_section(_SECTION):
        cfg.add_section(_SECTION)

    payload = asdict(settings)
    payload["playlist_paths"] = json.dumps(list(settings.playlist_paths), ensure_ascii=False)
    for key, value in payload.items():
        cfg.set(_SECTION, key, str(value))

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        cfg.write(handle)

    ConfigHelper._campaign_config = cfg
    ConfigHelper._campaign_mtime = path.stat().st_mtime


def update_ambiance_settings(**changes) -> AmbianceSettings:
    """Load current settings, apply partial updates and persist immediately."""
    current = load_ambiance_settings()
    merged = AmbianceSettings(**(asdict(current) | changes))
    if isinstance(merged.playlist_paths, list):
        merged.playlist_paths = tuple(merged.playlist_paths)
    save_ambiance_settings(merged)
    return merged


def _parse_playlist_paths(raw_value) -> tuple[str, ...]:
    if isinstance(raw_value, (list, tuple)):
        return tuple(str(item).strip() for item in raw_value if str(item).strip())
    if raw_value is None:
        return ()
    text = str(raw_value).strip()
    if not text:
        return ()
    try:
        decoded = json.loads(text)
    except Exception:
        return (text,)
    if isinstance(decoded, list):
        return tuple(str(item).strip() for item in decoded if str(item).strip())
    return ()


def _to_bool(value, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    normalized = str(value).strip().lower()
    if normalized in {"1", "yes", "true", "on"}:
        return True
    if normalized in {"0", "no", "false", "off"}:
        return False
    return default


def _to_float(value, default: float) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _to_int(value, default: int) -> int:
    try:
        return int(value)
    except Exception:
        return default
