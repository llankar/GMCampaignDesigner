"""Apply an authenticated delta payload to a staged campaign copy."""
from __future__ import annotations

import os
import shutil
from pathlib import Path

from .delta_manifest import DeltaManifest, normalize_sync_path
from .hashing import sha256_file


def _safe_staging_path(staging: Path, relative: str) -> Path:
    """Resolve a manifest path and reject traversal through existing symlinks."""
    root = staging.resolve()
    candidate = (root / normalize_sync_path(relative)).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"delta path escapes campaign root: {relative!r}") from exc
    return candidate


def clone_campaign(source: Path, destination: Path) -> None:
    def copy(source_name: str, destination_name: str) -> str:
        try:
            os.link(source_name, destination_name)
            return destination_name
        except OSError:
            return shutil.copy2(source_name, destination_name)
    shutil.copytree(source, destination, copy_function=copy)


def apply_delta(extracted: Path, staging: Path, delta: DeltaManifest, database_meta: dict) -> Path:
    for relative in delta.tombstones:
        target = _safe_staging_path(staging, relative)
        if target.is_dir():
            raise ValueError(f"delta tombstone names a directory: {relative}")
        target.unlink(missing_ok=True)
    for entry in delta.files:
        source = extracted / "payload" / entry.path
        if not source.is_file() or source.stat().st_size != entry.size or sha256_file(source) != entry.sha256:
            raise ValueError(f"corrupted delta payload: {entry.path}")
        target = _safe_staging_path(staging, entry.path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.unlink(missing_ok=True)  # detach a possible hard link to active
        shutil.copy2(source, target)
    source_db = extracted / str(database_meta["relative_path"])
    if not source_db.is_file() or sha256_file(source_db) != str(database_meta["sha256"]):
        raise ValueError("corrupted delta database snapshot")
    file_name = normalize_sync_path(str(database_meta["file_name"]))
    if "/" in file_name:
        raise ValueError("delta database file_name must be a file name")
    target_db = _safe_staging_path(staging, file_name)
    target_db.unlink(missing_ok=True)  # never mutate the active database inode
    shutil.copy2(source_db, target_db)
    return target_db
