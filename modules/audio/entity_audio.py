"""Utility helpers for playing entity-specific audio cues."""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Optional

from modules.audio.audio_player import AudioPlayer
from modules.helpers.config_helper import ConfigHelper
from modules.helpers.logging_helper import (
    log_exception,
    log_info,
    log_module_import,
    log_warning,
)

log_module_import(__name__)

_ENTITY_PLAYER: Optional[AudioPlayer] = None


def normalize_audio_reference(value: Any) -> str:
    """Normalize stored audio metadata into a plain string reference."""

    if not value:
        return ""
    if isinstance(value, Mapping):
        for key in ("path", "text", "value", "url"):
            candidate = value.get(key)
            if candidate:
                try:
                    return str(candidate).strip()
                except Exception:
                    continue
        return ""
    try:
        return str(value).strip()
    except Exception:
        return ""


def get_entity_audio_value(record: Any) -> str:
    """Extract an audio reference from an entity record or value."""

    if isinstance(record, Mapping):
        return normalize_audio_reference(record.get("Audio"))
    return normalize_audio_reference(record)


def _get_player() -> AudioPlayer:
    global _ENTITY_PLAYER
    if _ENTITY_PLAYER is None:
        _ENTITY_PLAYER = AudioPlayer()
    return _ENTITY_PLAYER


def resolve_audio_path(value: str | os.PathLike[str]) -> str:
    """Return an absolute path for an audio reference stored in the campaign."""
    if not value:
        return ""
    try:
        candidate = Path(value)
    except TypeError:
        return ""
    if candidate.is_absolute():
        return str(candidate)
    base = Path(ConfigHelper.get_campaign_dir())
    return str((base / candidate).resolve())


def play_entity_audio(value: str | os.PathLike[str], *, entity_label: str = "") -> bool:
    """Play a single audio track associated with an entity.

    Parameters
    ----------
    value:
        Path (relative or absolute) to the audio file.
    entity_label:
        Friendly name used in log output and UI messages.
    """
    path = resolve_audio_path(value)
    if not path:
        log_warning(
            "play_entity_audio - no audio path supplied",
            func_name="play_entity_audio",
        )
        return False
    if not os.path.exists(path):
        log_warning(
            f"play_entity_audio - file not found: {path}",
            func_name="play_entity_audio",
        )
        return False

    player = _get_player()
    try:
        player.stop()
    except Exception as exc:  # pragma: no cover - defensive
        log_warning(
            f"play_entity_audio - stop failed before replay: {exc}",
            func_name="play_entity_audio",
        )

    track = {
        "id": path,
        "name": entity_label or os.path.splitext(os.path.basename(path))[0],
        "path": path,
    }

    try:
        player.set_playlist([track])
        success = player.play(start_index=0)
    except Exception as exc:  # pragma: no cover - backend failure
        log_exception(
            f"play_entity_audio - playback raised exception: {exc}",
            func_name="play_entity_audio",
        )
        return False

    if success:
        log_info(
            f"play_entity_audio - playing '{track['name']}'",
            func_name="play_entity_audio",
        )
    else:
        log_warning(
            f"play_entity_audio - failed to start playback: {player.last_error}",
            func_name="play_entity_audio",
        )
    return success


def stop_entity_audio() -> None:
    """Stop the currently playing entity audio track, if any."""
    if _ENTITY_PLAYER is None:
        return
    try:
        _ENTITY_PLAYER.stop()
    except Exception as exc:  # pragma: no cover - defensive
        log_warning(
            f"stop_entity_audio - stop failed: {exc}",
            func_name="stop_entity_audio",
        )

__all__ = [
    "get_entity_audio_value",
    "normalize_audio_reference",
    "play_entity_audio",
    "resolve_audio_path",
    "stop_entity_audio",
]
