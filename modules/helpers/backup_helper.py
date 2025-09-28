"""Utilities for creating and restoring campaign backup archives."""

from __future__ import annotations

import datetime as _dt
import json
import os
import re
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Callable, Iterable, Optional

from modules.helpers.config_helper import ConfigHelper
from modules.helpers.logging_helper import (
    log_debug,
    log_exception,
    log_info,
    log_module_import,
    log_warning,
)

ProgressCallback = Callable[[str, float], None]

BACKUP_MANIFEST_NAME = "backup_manifest.json"
BACKUP_FORMAT_VERSION = 1

_VERSION_PATTERN = re.compile(r"StringStruct\('FileVersion',\s*'([^']+)'\)")


class BackupError(Exception):
    """Raised when a backup operation cannot be completed."""


class ManifestError(BackupError):
    """Raised when a backup manifest is missing or incompatible."""


def _call_progress(callback: Optional[ProgressCallback], message: str, fraction: float) -> None:
    if callback is None:
        return
    try:
        callback(message, max(0.0, min(1.0, float(fraction))))
    except Exception as exc:  # pragma: no cover - defensive
        log_warning(
            f"Progress callback failed: {exc}",
            func_name="modules.helpers.backup_helper._call_progress",
        )


def _read_app_version() -> str:
    version_file = Path("version.txt")
    if not version_file.exists():
        return "unknown"
    try:
        text = version_file.read_text(encoding="utf-8", errors="ignore")
    except Exception as exc:  # pragma: no cover - best effort only
        log_warning(
            f"Unable to read version.txt: {exc}",
            func_name="modules.helpers.backup_helper._read_app_version",
        )
        return "unknown"
    match = _VERSION_PATTERN.search(text)
    return match.group(1) if match else "unknown"


def _relative_arcname(path: Path, base: Path) -> str:
    try:
        rel = path.resolve().relative_to(base.resolve())
    except Exception:
        rel = Path(path.name)
    return str(rel).replace(os.sep, "/")


def _iter_files(root: Path) -> Iterable[Path]:
    for entry in sorted(root.rglob("*")):
        if entry.is_file():
            yield entry


def _resolve_database_path() -> Path:
    db_value = ConfigHelper.get("Database", "path", fallback="campaign.db") or "campaign.db"
    db_path = Path(db_value)
    if db_path.exists() and db_path.is_file():
        return db_path.resolve()

    campaign_dir_str = ConfigHelper.get_campaign_dir()
    campaign_dir = Path(campaign_dir_str) if campaign_dir_str else None
    if campaign_dir is None:
        return db_path.resolve()

    # First try relative to the campaign directory.
    candidate = (campaign_dir / db_path.name).resolve()
    if candidate.exists():
        return candidate

    candidate = (campaign_dir / db_path).resolve()
    if candidate.exists():
        return candidate

    # Fall back to absolute resolution relative to cwd.
    return db_path.resolve()


def create_backup_archive(
    destination_path: str | os.PathLike[str],
    progress_callback: Optional[ProgressCallback] = None,
) -> dict:
    """Create a zip archive containing campaign data and return its manifest."""

    destination = Path(destination_path)
    parent_dir = destination.parent
    if not parent_dir.exists():
        raise BackupError(f"Destination directory does not exist: {parent_dir}")

    campaign_dir = Path(ConfigHelper.get_campaign_dir()).resolve()
    if not campaign_dir.exists():
        raise BackupError(f"Campaign directory not found: {campaign_dir}")

    _call_progress(progress_callback, "Collecting campaign files...", 0.0)

    db_path = _resolve_database_path()
    if not db_path.exists():
        raise BackupError(f"Database file not found: {db_path}")

    sources: list[tuple[Path, str]] = []
    missing: list[str] = []

    def add_file(path: Path) -> None:
        if path.exists() and path.is_file():
            sources.append((path, _relative_arcname(path, campaign_dir)))
        else:
            missing.append(str(path))
            log_warning(
                f"Skipping missing file during backup: {path}",
                func_name="modules.helpers.backup_helper.create_backup_archive",
            )

    def add_directory(path: Path) -> None:
        if not path.exists():
            missing.append(str(path))
            log_warning(
                f"Skipping missing directory during backup: {path}",
                func_name="modules.helpers.backup_helper.create_backup_archive",
            )
            return
        for item in _iter_files(path):
            sources.append((item, _relative_arcname(item, campaign_dir)))

    add_file(db_path)
    add_file(campaign_dir / "settings.ini")
    add_directory(campaign_dir / "templates")
    add_directory(campaign_dir / "assets")

    if not sources:
        raise BackupError("No files found to include in the backup.")

    manifest = {
        "format_version": BACKUP_FORMAT_VERSION,
        "app_version": _read_app_version(),
        "created_at": _dt.datetime.utcnow().isoformat() + "Z",
        "campaign_directory": str(campaign_dir),
        "campaign_name": campaign_dir.name,
        "database_path": str(db_path),
        "files": [
            {
                "path": arcname,
                "size": src.stat().st_size,
            }
            for src, arcname in sources
        ],
        "missing": missing,
    }

    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".tmp", dir=str(parent_dir))
    os.close(tmp_fd)

    success = False
    try:
        with zipfile.ZipFile(tmp_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            total_items = len(sources) + 1  # Manifest counts as last step.
            for index, (src, arcname) in enumerate(sources, start=1):
                _call_progress(
                    progress_callback,
                    f"Adding {arcname}",
                    index / total_items,
                )
                zf.write(src, arcname)
            zf.writestr(BACKUP_MANIFEST_NAME, json.dumps(manifest, indent=2))
            _call_progress(progress_callback, "Finalizing archive...", 1.0)
        success = True
    except PermissionError as exc:
        raise PermissionError(f"Unable to write backup archive: {exc}") from exc
    except Exception as exc:
        log_exception(
            f"Failed to create backup archive: {exc}",
            func_name="modules.helpers.backup_helper.create_backup_archive",
        )
        raise BackupError(f"Failed to create backup archive: {exc}") from exc
    finally:
        if not success and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:  # pragma: no cover - defensive cleanup
                log_warning(
                    "Failed to remove temporary backup file during cleanup.",
                    func_name="modules.helpers.backup_helper.create_backup_archive",
                )

    try:
        os.replace(tmp_path, destination)
    except PermissionError as exc:
        os.remove(tmp_path)
        raise PermissionError(f"Unable to move backup archive into place: {exc}") from exc
    except Exception as exc:
        os.remove(tmp_path)
        log_exception(
            f"Failed to finalize backup archive: {exc}",
            func_name="modules.helpers.backup_helper.create_backup_archive",
        )
        raise BackupError(f"Failed to finalize backup archive: {exc}") from exc

    manifest["archive_path"] = str(destination)
    log_info(
        f"Backup archive created with {len(sources)} files at {destination}",
        func_name="modules.helpers.backup_helper.create_backup_archive",
    )
    if missing:
        log_debug(
            f"Backup skipped {len(missing)} missing paths",
            func_name="modules.helpers.backup_helper.create_backup_archive",
        )
    return manifest


def restore_backup_archive(
    archive_path: str | os.PathLike[str],
    target_dir: Optional[str | os.PathLike[str]] = None,
    progress_callback: Optional[ProgressCallback] = None,
) -> dict:
    """Restore a campaign backup archive into ``target_dir`` and return the manifest."""

    archive = Path(archive_path)
    if not archive.exists():
        raise BackupError(f"Backup archive not found: {archive}")

    destination = Path(target_dir or ConfigHelper.get_campaign_dir()).resolve()
    if not destination.exists():
        destination.mkdir(parents=True, exist_ok=True)

    _call_progress(progress_callback, "Reading backup manifest...", 0.0)

    try:
        with zipfile.ZipFile(archive, "r") as zf:
            try:
                manifest_data = json.loads(zf.read(BACKUP_MANIFEST_NAME))
            except KeyError as exc:
                raise ManifestError("Backup manifest missing from archive.") from exc
            except json.JSONDecodeError as exc:
                raise ManifestError("Backup manifest is corrupted.") from exc

            if manifest_data.get("format_version") != BACKUP_FORMAT_VERSION:
                raise ManifestError("Backup archive format is not supported.")

            members = [
                name for name in zf.namelist()
                if name != BACKUP_MANIFEST_NAME and not name.endswith("/")
            ]
            total = max(len(members), 1)

            for index, name in enumerate(members, start=1):
                _call_progress(
                    progress_callback,
                    f"Restoring {name}",
                    index / total,
                )
                member_path = destination.joinpath(Path(name))
                resolved_target = member_path.resolve()
                common = os.path.commonpath([str(destination), str(resolved_target)])
                if common != str(destination):
                    raise ManifestError(f"Archive entry escapes target directory: {name}")

                member_path.parent.mkdir(parents=True, exist_ok=True)
                try:
                    with zf.open(name, "r") as src, open(resolved_target, "wb") as dst:
                        shutil.copyfileobj(src, dst)
                except PermissionError as exc:
                    raise PermissionError(
                        f"Permission denied while restoring '{name}': {exc}"
                    ) from exc
            _call_progress(progress_callback, "Restore complete", 1.0)
    except PermissionError:
        raise
    except ManifestError:
        raise
    except BackupError:
        raise
    except Exception as exc:
        log_exception(
            f"Failed to restore backup archive: {exc}",
            func_name="modules.helpers.backup_helper.restore_backup_archive",
        )
        raise BackupError(f"Failed to restore backup archive: {exc}") from exc

    manifest_data["archive_path"] = str(archive)
    manifest_data["restored_to"] = str(destination)
    log_info(
        f"Restored backup archive {archive} into {destination}",
        func_name="modules.helpers.backup_helper.restore_backup_archive",
    )
    return manifest_data


log_module_import(__name__)
