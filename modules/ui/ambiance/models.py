"""Data models used by the ambiance second-screen player."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

AmbianceMediaType = Literal["image", "video"]


@dataclass(slots=True)
class AmbianceItem:
    """Single ambiance media entry."""

    path: str
    media_type: AmbianceMediaType = "image"
    duration: float = 8.0
    tags: tuple[str, ...] = field(default_factory=tuple)


@dataclass(slots=True)
class AmbiancePlaylist:
    """Collection of ambiance media items and playback options."""

    items: list[AmbianceItem] = field(default_factory=list)
    loop: bool = True
    shuffle: bool = False
    default_duration: float = 8.0
    transition_ms: int = 380


@dataclass(slots=True)
class AmbianceState:
    """Runtime state for the ambiance player."""

    is_running: bool = False
    is_paused: bool = False
    current_index: int = -1
    after_id: str | None = None
    video_after_id: str | None = None
    slide_started_at: float = 0.0
