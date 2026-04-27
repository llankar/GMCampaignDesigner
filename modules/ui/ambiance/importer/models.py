"""Models for ambiance wallpaper import workflow."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from modules.ui.ambiance.library.models import WallpaperLibraryItem

DuplicateStrategy = Literal["skip", "replace", "keep_both"]
ImportStatus = Literal["pending", "imported", "skipped", "failed"]


@dataclass(slots=True)
class ImportCandidate:
    """Single user-selected file candidate."""

    source_path: str
    filename: str
    filesize: int = 0
    width: int | None = None
    height: int | None = None
    media_type: str = "unknown"
    status: ImportStatus = "pending"
    message: str = ""


@dataclass(slots=True)
class ImportResult:
    """Summary returned by import service."""

    entries: list[ImportCandidate] = field(default_factory=list)
    imported_items: list[WallpaperLibraryItem] = field(default_factory=list)

    @property
    def imported_count(self) -> int:
        return sum(1 for entry in self.entries if entry.status == "imported")

    @property
    def skipped_count(self) -> int:
        return sum(1 for entry in self.entries if entry.status == "skipped")

    @property
    def failed_count(self) -> int:
        return sum(1 for entry in self.entries if entry.status == "failed")
