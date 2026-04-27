"""Media repository for the GM Table ambiance workspace."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from PIL import Image

_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp"}
_VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"}
_MEDIA_EXTENSIONS = _IMAGE_EXTENSIONS | _VIDEO_EXTENSIONS


@dataclass(slots=True)
class AmbianceMediaRecord:
    """Single indexed media entry."""

    path: str
    name: str
    media_type: str
    modified_at: float
    size_bytes: int
    width: int | None = None
    height: int | None = None


class AmbianceMediaRepository:
    """Build a local media index from folders or explicit paths."""

    def scan_folder(self, folder_path: str) -> list[AmbianceMediaRecord]:
        """Scan a folder recursively and return indexed media entries."""
        base = Path(folder_path).expanduser()
        if not base.is_dir():
            return []

        records: list[AmbianceMediaRecord] = []
        for candidate in sorted(base.rglob("*")):
            if not candidate.is_file() or candidate.suffix.lower() not in _MEDIA_EXTENSIONS:
                continue
            record = self._build_record(candidate)
            if record is not None:
                records.append(record)
        return records

    def build_index(self, media_paths: Iterable[str]) -> list[AmbianceMediaRecord]:
        """Create metadata records from an explicit list of media paths."""
        records: list[AmbianceMediaRecord] = []
        for raw_path in media_paths:
            path = Path(str(raw_path or "")).expanduser()
            if not path.is_file() or path.suffix.lower() not in _MEDIA_EXTENSIONS:
                continue
            record = self._build_record(path)
            if record is not None:
                records.append(record)
        return sorted(records, key=lambda entry: entry.name.casefold())

    def _build_record(self, path: Path) -> AmbianceMediaRecord | None:
        try:
            stat = path.stat()
        except OSError:
            return None

        extension = path.suffix.lower()
        media_type = "image" if extension in _IMAGE_EXTENSIONS else "video"
        width = None
        height = None

        if media_type == "image":
            try:
                with Image.open(path) as image:
                    width, height = image.size
            except Exception:
                width = None
                height = None

        return AmbianceMediaRecord(
            path=str(path.resolve()),
            name=path.name,
            media_type=media_type,
            modified_at=float(stat.st_mtime),
            size_bytes=int(stat.st_size),
            width=width,
            height=height,
        )
