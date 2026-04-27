"""Import logic for campaign-local ambiance wallpapers."""

from __future__ import annotations

import re
import shutil
from pathlib import Path
from uuid import uuid4

from PIL import Image

from modules.ui.ambiance.importer.models import DuplicateStrategy, ImportCandidate, ImportResult
from modules.ui.ambiance.library.index_store import CampaignWallpaperIndexStore
from modules.ui.ambiance.library.models import WallpaperLibraryItem

_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp"}
_VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"}
_MEDIA_EXTENSIONS = _IMAGE_EXTENSIONS | _VIDEO_EXTENSIONS
_NAME_SANITIZE_PATTERN = re.compile(r"[^a-zA-Z0-9._\- ]+")


class WallpaperImportService:
    """Validate and copy user-selected files into campaign wallpaper storage."""

    def __init__(self, index_store: CampaignWallpaperIndexStore | None = None) -> None:
        self._store = index_store or CampaignWallpaperIndexStore()

    def inspect_candidates(self, paths: list[str] | tuple[str, ...]) -> list[ImportCandidate]:
        candidates: list[ImportCandidate] = []
        for raw in paths:
            path = Path(str(raw or "")).expanduser()
            if not path.exists() or not path.is_file():
                candidates.append(
                    ImportCandidate(
                        source_path=str(path),
                        filename=path.name or str(path),
                        status="failed",
                        message="File not found.",
                    )
                )
                continue

            media_type = _infer_media_type(path)
            if media_type is None:
                candidates.append(
                    ImportCandidate(
                        source_path=str(path),
                        filename=path.name,
                        filesize=int(path.stat().st_size),
                        status="failed",
                        message="Unsupported file type.",
                    )
                )
                continue

            width = None
            height = None
            if media_type == "image":
                try:
                    with Image.open(path) as image:
                        width, height = image.size
                except Exception:
                    width = None
                    height = None

            candidates.append(
                ImportCandidate(
                    source_path=str(path.resolve()),
                    filename=path.name,
                    filesize=int(path.stat().st_size),
                    width=width,
                    height=height,
                    media_type=media_type,
                    status="pending",
                )
            )
        return candidates

    def import_files(self, paths: list[str] | tuple[str, ...], *, strategy: DuplicateStrategy = "skip") -> ImportResult:
        entries = self.inspect_candidates(paths)
        existing = self._store.load()
        by_filename = {item.filename.casefold(): item for item in existing}
        imported_items: list[WallpaperLibraryItem] = []

        for entry in entries:
            if entry.status == "failed":
                continue
            source = Path(entry.source_path)
            if not source.exists() or not source.is_file():
                entry.status = "failed"
                entry.message = "Source file missing."
                continue

            safe_name = sanitize_filename(entry.filename)
            duplicate = by_filename.get(safe_name.casefold())
            destination = self._store.wallpapers_dir / safe_name

            if duplicate and strategy == "skip":
                entry.status = "skipped"
                entry.message = "Skipped (duplicate filename)."
                continue

            if duplicate and strategy == "keep_both":
                destination = self._store.next_unique_path(safe_name)
                safe_name = destination.name
                duplicate = None

            try:
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)
            except Exception as exc:
                entry.status = "failed"
                entry.message = f"Copy failed: {exc}"
                continue

            library_item = _build_item(destination, source_media_type=entry.media_type, previous=duplicate)
            imported_items.append(library_item)
            by_filename[library_item.filename.casefold()] = library_item
            entry.filename = library_item.filename
            entry.filesize = library_item.filesize
            entry.width = library_item.width
            entry.height = library_item.height
            entry.media_type = library_item.media_type
            entry.status = "imported"
            entry.message = "Imported"

        self._store.upsert_many(imported_items)
        return ImportResult(entries=entries, imported_items=imported_items)


def sanitize_filename(name: str) -> str:
    """Normalize imported filenames to safe local asset names."""
    original = Path(name).name.strip() or "wallpaper"
    cleaned = _NAME_SANITIZE_PATTERN.sub("_", original)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .")
    if not cleaned:
        cleaned = "wallpaper"
    if "." not in cleaned:
        cleaned = f"{cleaned}.png"
    return cleaned


def _infer_media_type(path: Path) -> str | None:
    suffix = path.suffix.lower()
    if suffix in _IMAGE_EXTENSIONS:
        return "image"
    if suffix in _VIDEO_EXTENSIONS:
        return "video"
    return None


def _build_item(destination: Path, *, source_media_type: str, previous: WallpaperLibraryItem | None) -> WallpaperLibraryItem:
    stat = destination.stat()
    media_type = source_media_type if source_media_type in {"image", "video"} else (_infer_media_type(destination) or "image")
    width = None
    height = None
    if media_type == "image":
        try:
            with Image.open(destination) as image:
                width, height = image.size
        except Exception:
            width = None
            height = None

    return WallpaperLibraryItem(
        id=(previous.id if previous else uuid4().hex),
        relative_path=destination.name,
        filename=destination.name,
        media_type=("video" if media_type == "video" else "image"),
        width=width,
        height=height,
        filesize=int(stat.st_size),
        created_at=float(stat.st_mtime),
        tags=(previous.tags if previous else ()),
    )
