"""Models for campaign-local ambiance wallpaper library."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

MediaType = Literal["image", "video"]
SortKey = Literal["name", "created_desc", "created_asc", "size_desc", "size_asc"]


@dataclass(slots=True)
class WallpaperLibraryItem:
    """Persisted library record for a single campaign media item."""

    id: str
    relative_path: str
    filename: str
    media_type: MediaType
    width: int | None
    height: int | None
    filesize: int
    created_at: float
    tags: tuple[str, ...] = field(default_factory=tuple)


@dataclass(slots=True)
class WallpaperQuery:
    """Library query options used by the ambiance page."""

    search: str = ""
    tags: tuple[str, ...] = field(default_factory=tuple)
    orientation: str = "all"
    media_type: str = "all"
    sort_key: SortKey = "name"
