"""Bundle helpers for campaign ambiance wallpaper library assets."""

from __future__ import annotations

import json
import shutil
from pathlib import Path, PurePosixPath
from typing import Any

from modules.ui.ambiance.library.index_store import CampaignWallpaperIndexStore
from modules.ui.ambiance.library.models import WallpaperLibraryItem

BUNDLE_DIR = Path("ambiance_wallpapers")
FILES_DIR_NAME = "files"
INDEX_FILE_NAME = "index.json"
MANIFEST_KEY = "ambiance_wallpapers"


def export_wallpaper_bundle(campaign_root: Path, bundle_root: Path) -> dict[str, Any] | None:
    """Copy wallpaper media/metadata into a bundle staging root and return manifest metadata."""
    store = CampaignWallpaperIndexStore(str(campaign_root))
    items = _valid_existing_items(store)
    if not items:
        return None

    bundle_dir = bundle_root / BUNDLE_DIR
    bundle_files_dir = bundle_dir / FILES_DIR_NAME
    entries: list[dict[str, Any]] = []

    for item in items:
        source = Path(store.absolute_path(item))
        safe_relative = _safe_relative_path(item.relative_path)
        if (
            safe_relative is None
            or not _is_within(source, store.wallpapers_dir)
            or not source.exists()
            or not source.is_file()
        ):
            continue

        destination = bundle_files_dir / safe_relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        entries.append(_item_to_manifest_entry(item))

    if not entries:
        return None

    index_path = bundle_dir / INDEX_FILE_NAME
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text(
        json.dumps({"version": 1, "items": entries}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    return {
        "count": len(entries),
        "index_path": (BUNDLE_DIR / INDEX_FILE_NAME).as_posix(),
        "files_path": (BUNDLE_DIR / FILES_DIR_NAME).as_posix(),
        "items": entries,
    }


def load_wallpaper_manifest(bundle_root: Path, manifest: dict[str, Any]) -> list[dict[str, Any]]:
    """Load wallpaper metadata entries from an extracted bundle."""
    section = manifest.get(MANIFEST_KEY)
    if not isinstance(section, dict):
        return []

    raw_items = section.get("items")
    if isinstance(raw_items, list):
        return [_entry for item in raw_items if (_entry := _normalize_entry(item)) is not None]

    index_path_value = str(section.get("index_path") or "").strip()
    if not index_path_value:
        return []
    safe_index_path = _safe_relative_path(index_path_value)
    if safe_index_path is None:
        return []
    index_path = bundle_root / safe_index_path
    if not _is_within(index_path, bundle_root) or not index_path.exists():
        return []

    try:
        payload = json.loads(index_path.read_text(encoding="utf-8"))
    except Exception:
        return []
    items = payload.get("items") if isinstance(payload, dict) else None
    if not isinstance(items, list):
        return []
    return [_entry for item in items if (_entry := _normalize_entry(item)) is not None]


def merge_wallpaper_bundle(
    bundle_root: Path,
    target_campaign_root: Path,
    entries: list[dict[str, Any]],
    *,
    overwrite: bool,
) -> dict[str, int]:
    """Restore bundled wallpaper files and merge them into the target campaign index."""
    summary = {
        "ambiance_wallpapers_imported": 0,
        "ambiance_wallpapers_updated": 0,
        "ambiance_wallpapers_skipped": 0,
    }
    if not entries:
        return summary

    store = CampaignWallpaperIndexStore(str(target_campaign_root))
    existing_items = store.load()
    by_id = {item.id: item for item in existing_items if item.id}
    by_relative = {item.relative_path: item for item in existing_items if item.relative_path}
    merged_by_id = {item.id: item for item in existing_items if item.id}

    for entry in entries:
        relative_path = entry["relative_path"]
        safe_relative = _safe_relative_path(relative_path)
        if safe_relative is None:
            summary["ambiance_wallpapers_skipped"] += 1
            continue

        source = bundle_root / BUNDLE_DIR / FILES_DIR_NAME / safe_relative
        destination = store.wallpapers_dir / safe_relative
        existing = by_relative.get(relative_path) or by_id.get(entry["id"])

        if (existing or destination.exists()) and not overwrite:
            summary["ambiance_wallpapers_skipped"] += 1
            continue
        if not source.exists() or not source.is_file():
            summary["ambiance_wallpapers_skipped"] += 1
            continue

        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)

        item = _entry_to_item(entry)
        if existing:
            merged_by_id.pop(existing.id, None)
            summary["ambiance_wallpapers_updated"] += 1
        else:
            summary["ambiance_wallpapers_imported"] += 1
        merged_by_id[item.id] = item
        by_id[item.id] = item
        by_relative[item.relative_path] = item

    store.save(list(merged_by_id.values()))
    return summary


def install_wallpaper_bundle(bundle_root: Path, target_campaign_root: Path, manifest: dict[str, Any]) -> dict[str, int]:
    """Restore bundled wallpapers during full campaign installation."""
    entries = load_wallpaper_manifest(bundle_root, manifest)
    return merge_wallpaper_bundle(bundle_root, target_campaign_root, entries, overwrite=True)


def _valid_existing_items(store: CampaignWallpaperIndexStore) -> list[WallpaperLibraryItem]:
    items: list[WallpaperLibraryItem] = []
    for item in store.load():
        if _safe_relative_path(item.relative_path) is None:
            continue
        source = Path(store.absolute_path(item))
        if source.exists() and source.is_file():
            items.append(item)
    return items


def _item_to_manifest_entry(item: WallpaperLibraryItem) -> dict[str, Any]:
    return {
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


def _entry_to_item(entry: dict[str, Any]) -> WallpaperLibraryItem:
    return WallpaperLibraryItem(
        id=entry["id"],
        relative_path=entry["relative_path"],
        filename=entry["filename"],
        media_type="video" if entry.get("media_type") == "video" else "image",
        width=_to_optional_int(entry.get("width")),
        height=_to_optional_int(entry.get("height")),
        filesize=max(0, _to_int(entry.get("filesize"), 0)),
        created_at=_to_float(entry.get("created_at"), 0.0),
        tags=tuple(str(tag).strip() for tag in entry.get("tags", []) if str(tag).strip())
        if isinstance(entry.get("tags"), list)
        else (),
    )


def _normalize_entry(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    relative_path = str(raw.get("relative_path") or "").replace("\\", "/").strip()
    item_id = str(raw.get("id") or "").strip()
    filename = str(raw.get("filename") or Path(relative_path).name).strip()
    if not relative_path or not item_id or not filename or _safe_relative_path(relative_path) is None:
        return None
    tags_raw = raw.get("tags")
    tags = [str(tag).strip() for tag in tags_raw if str(tag).strip()] if isinstance(tags_raw, list) else []
    return {
        "id": item_id,
        "relative_path": relative_path,
        "filename": filename,
        "media_type": "video" if str(raw.get("media_type") or "").lower() == "video" else "image",
        "width": _to_optional_int(raw.get("width")),
        "height": _to_optional_int(raw.get("height")),
        "filesize": max(0, _to_int(raw.get("filesize"), 0)),
        "created_at": _to_float(raw.get("created_at"), 0.0),
        "tags": tags,
    }


def _safe_relative_path(value: str) -> Path | None:
    normalized = str(value or "").replace("\\", "/").strip()
    if not normalized:
        return None
    path = PurePosixPath(normalized)
    if path.is_absolute() or any(part in ("", ".", "..") or ":" in part for part in path.parts):
        return None
    return Path(*path.parts)


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _to_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _to_optional_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except Exception:
        return None
