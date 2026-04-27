"""Campaign-local persistence for ambiance wallpaper index metadata."""

from __future__ import annotations

import json
import os
from pathlib import Path
from uuid import uuid4

from PIL import Image

from modules.helpers.config_helper import ConfigHelper
from modules.ui.ambiance.library.models import WallpaperLibraryItem

_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp"}
_VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"}
_MEDIA_EXTENSIONS = _IMAGE_EXTENSIONS | _VIDEO_EXTENSIONS


class CampaignWallpaperIndexStore:
    """Read/write wallpaper index in active campaign folder."""

    def __init__(self, campaign_dir: str | None = None) -> None:
        base = Path(campaign_dir or ConfigHelper.get_campaign_dir())
        self._campaign_dir = base
        self._wallpapers_dir = base / "assets" / "ambiance" / "wallpapers"
        self._index_path = self._wallpapers_dir / "index.json"

    @property
    def wallpapers_dir(self) -> Path:
        self._wallpapers_dir.mkdir(parents=True, exist_ok=True)
        return self._wallpapers_dir

    @property
    def index_path(self) -> Path:
        self.wallpapers_dir.mkdir(parents=True, exist_ok=True)
        return self._index_path

    def load(self) -> list[WallpaperLibraryItem]:
        path = self.index_path
        if not path.exists():
            return []
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return []
        raw_items = payload.get("items") if isinstance(payload, dict) else []
        if not isinstance(raw_items, list):
            return []

        rows: list[WallpaperLibraryItem] = []
        for raw in raw_items:
            if not isinstance(raw, dict):
                continue
            row = WallpaperLibraryItem(
                id=str(raw.get("id") or uuid4().hex),
                relative_path=str(raw.get("relative_path") or "").replace("\\", "/"),
                filename=str(raw.get("filename") or ""),
                media_type=("video" if str(raw.get("media_type") or "").lower() == "video" else "image"),
                width=_to_int(raw.get("width")),
                height=_to_int(raw.get("height")),
                filesize=max(0, _to_int(raw.get("filesize"), 0) or 0),
                created_at=float(raw.get("created_at") or 0.0),
                tags=tuple(_clean_tags(raw.get("tags"))),
            )
            if row.relative_path and row.filename:
                rows.append(row)
        return rows

    def save(self, items: list[WallpaperLibraryItem]) -> None:
        payload = {
            "version": 1,
            "items": [
                {
                    "id": item.id,
                    "relative_path": item.relative_path,
                    "filename": item.filename,
                    "media_type": item.media_type,
                    "width": item.width,
                    "height": item.height,
                    "filesize": item.filesize,
                    "created_at": item.created_at,
                    "tags": list(item.tags),
                }
                for item in items
            ],
        }
        path = self.index_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def upsert(self, item: WallpaperLibraryItem) -> WallpaperLibraryItem:
        rows = self.load()
        by_id = {row.id: row for row in rows}
        by_id[item.id] = item
        self.save(list(by_id.values()))
        return item

    def upsert_many(self, items: list[WallpaperLibraryItem]) -> list[WallpaperLibraryItem]:
        if not items:
            return []
        rows = self.load()
        by_id = {row.id: row for row in rows}
        for item in items:
            by_id[item.id] = item
        merged = list(by_id.values())
        self.save(merged)
        return items

    def rebuild(self) -> list[WallpaperLibraryItem]:
        indexed_by_rel = {item.relative_path: item for item in self.load()}
        rebuilt: list[WallpaperLibraryItem] = []
        for candidate in sorted(self.wallpapers_dir.rglob("*")):
            if not candidate.is_file() or candidate.name == "index.json":
                continue
            suffix = candidate.suffix.lower()
            if suffix not in _MEDIA_EXTENSIONS:
                continue
            rel = candidate.relative_to(self.wallpapers_dir).as_posix()
            stat = candidate.stat()
            media_type = "image" if suffix in _IMAGE_EXTENSIONS else "video"
            width = None
            height = None
            if media_type == "image":
                try:
                    with Image.open(candidate) as image:
                        width, height = image.size
                except Exception:
                    width = None
                    height = None
            previous = indexed_by_rel.get(rel)
            rebuilt.append(
                WallpaperLibraryItem(
                    id=(previous.id if previous else uuid4().hex),
                    relative_path=rel,
                    filename=candidate.name,
                    media_type=media_type,
                    width=width,
                    height=height,
                    filesize=int(stat.st_size),
                    created_at=float(stat.st_mtime),
                    tags=(previous.tags if previous else ()),
                )
            )
        self.save(rebuilt)
        return rebuilt

    def absolute_path(self, item: WallpaperLibraryItem) -> str:
        return str((self.wallpapers_dir / item.relative_path).resolve())

    def next_unique_path(self, filename: str) -> Path:
        target = self.wallpapers_dir / filename
        if not target.exists():
            return target

        stem = target.stem
        suffix = target.suffix
        counter = 2
        while True:
            candidate = target.with_name(f"{stem}-{counter}{suffix}")
            if not candidate.exists():
                return candidate
            counter += 1


def _to_int(value, default: int | None = None) -> int | None:
    try:
        return int(value)
    except Exception:
        return default


def _clean_tags(raw_tags) -> tuple[str, ...]:
    if not isinstance(raw_tags, (list, tuple)):
        return ()
    cleaned: list[str] = []
    for tag in raw_tags:
        text = str(tag or "").strip()
        if text:
            cleaned.append(text)
    return tuple(cleaned)
