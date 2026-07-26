"""Canonical campaign fingerprints and conservative local-change detection.

Only content that participates in a full-campaign synchronization is included.
Sync bookkeeping and SQLite's transient sidecar files are deliberately excluded.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import sqlite3
import tempfile
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Iterable, Optional

from modules.generic.cross_campaign_bundle_extras import collect_full_campaign_extra_files

from .hashing import sha256_file
from .metadata_store import InstallationStateStore

_CONTENT_DIRECTORIES = (Path("assets"), Path("world_maps"))
_SQLITE_SIDECARS = ("-journal", "-shm", "-wal")
_TRANSIENT_NAMES = {".DS_Store", "Thumbs.db"}
_TRANSIENT_SUFFIXES = (".tmp", ".temp", ".part", ".swp", "~")


class CampaignChangeState(str, Enum):
    CLEAN = "clean"
    LOCALLY_MODIFIED = "locally_modified"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class CampaignChangeResult:
    state: CampaignChangeState
    current_fingerprint: Optional[str] = None
    baseline_fingerprint: Optional[str] = None
    error: Optional[str] = None

    @property
    def allows_one_click_replacement(self) -> bool:
        return self.state is CampaignChangeState.CLEAN


def _is_transient(path: Path) -> bool:
    name = path.name
    return (
        name in _TRANSIENT_NAMES
        or name.startswith(".~")
        or name.endswith(_SQLITE_SIDECARS)
        or any(name.endswith(suffix) for suffix in _TRANSIENT_SUFFIXES)
    )


def _database_path(root: Path, database_path: Optional[Path]) -> Path:
    if database_path is not None:
        candidate = Path(database_path)
        return (root / candidate).resolve() if not candidate.is_absolute() else candidate.resolve()
    candidates = sorted(
        (item.resolve() for item in root.glob("*.db") if item.is_file()),
        key=lambda item: item.name,
    )
    if len(candidates) != 1:
        raise ValueError(f"expected one campaign database in {root}, found {len(candidates)}")
    return candidates[0]


def sqlite_snapshot_sha256(database_path: Path) -> str:
    """Hash a transactionally consistent SQLite backup, never the live file."""
    source_path = Path(database_path).resolve()
    if not source_path.is_file():
        raise FileNotFoundError(source_path)
    descriptor, snapshot_name = tempfile.mkstemp(prefix="gmcd_fingerprint_", suffix=".db")
    os.close(descriptor)
    snapshot = Path(snapshot_name)
    try:
        source = sqlite3.connect(f"file:{source_path.as_posix()}?mode=ro", uri=True)
        destination = sqlite3.connect(str(snapshot))
        try:
            source.backup(destination)
        finally:
            destination.close()
            source.close()
        return sha256_file(snapshot)
    finally:
        snapshot.unlink(missing_ok=True)


def create_campaign_backup_archive(
    campaign_root: Path,
    destination: Path,
    *,
    database_path: Optional[Path] = None,
) -> Path:
    """Create a zip backup whose database member is a consistent snapshot.

    ``shutil.make_archive`` must not be pointed at a live campaign directly:
    copying a database while SQLite is writing can produce a corrupt backup.
    Stage the ordinary files first, then place a SQLite-backup copy of the
    database into the staged tree before creating the archive.
    """
    root = Path(campaign_root).expanduser().resolve()
    database = _database_path(root, database_path)
    try:
        database_relative = database.relative_to(root)
    except ValueError as exc:
        raise ValueError("campaign database must be inside the campaign root") from exc

    destination = Path(destination).expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="gmcd_campaign_backup_") as temp_name:
        staged = Path(temp_name) / root.name

        def ignore(directory: str, names: list[str]) -> set[str]:
            directory_path = Path(directory).resolve()
            ignored: set[str] = set()
            for name in names:
                candidate = directory_path / name
                if candidate == database or (
                    directory_path == database.parent
                    and name.startswith(database.name)
                    and name[len(database.name):] in _SQLITE_SIDECARS
                ):
                    ignored.add(name)
            return ignored

        shutil.copytree(root, staged, ignore=ignore)
        staged_database = staged / database_relative
        staged_database.parent.mkdir(parents=True, exist_ok=True)
        source = sqlite3.connect(f"file:{database.as_posix()}?mode=ro", uri=True)
        snapshot = sqlite3.connect(staged_database)
        try:
            source.backup(snapshot)
        finally:
            snapshot.close()
            source.close()

        archive_base = destination.with_suffix("") if destination.suffix.lower() == ".zip" else destination
        archive = Path(shutil.make_archive(str(archive_base), "zip", root_dir=staged))
        if archive != destination:
            shutil.move(str(archive), destination)
        return destination


def _content_files(root: Path) -> Iterable[tuple[Path, str]]:
    found: dict[str, Path] = {}
    for directory in _CONTENT_DIRECTORIES:
        base = root / directory
        if not base.is_dir():
            continue
        for item in base.rglob("*"):
            if item.is_file() and not _is_transient(item):
                found[item.relative_to(root).as_posix()] = item
    for item, relative in collect_full_campaign_extra_files(root):
        if item.is_file() and not _is_transient(item):
            found[Path(relative).as_posix()] = item
    return sorted(found.items(), key=lambda pair: pair[0])


def _normalized_relative_path(value: str) -> str:
    """Normalize and validate a path before it becomes part of the digest."""
    normalized = value.replace("\\", "/")
    path = Path(normalized)
    if path.is_absolute() or any(part in ("", ".", "..") for part in path.parts):
        raise ValueError(f"invalid synchronized-content path: {value!r}")
    return path.as_posix()


def calculate_campaign_fingerprint(
    campaign_root: Path, *, database_path: Optional[Path] = None
) -> str:
    """Return the canonical SHA-256 of normalized paths and content hashes."""
    root = Path(campaign_root).expanduser().resolve()
    database = _database_path(root, database_path)
    try:
        database_relative = database.relative_to(root).as_posix()
    except ValueError as exc:
        raise ValueError("campaign database must be inside the campaign root") from exc

    entries = [(_normalized_relative_path(database_relative), sqlite_snapshot_sha256(database))]
    entries.extend(
        (_normalized_relative_path(relative), sha256_file(path))
        for relative, path in _content_files(root)
    )
    digest = hashlib.sha256()
    for relative, file_digest in sorted(entries, key=lambda pair: pair[0]):
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(bytes.fromhex(file_digest))
        digest.update(b"\n")
    return digest.hexdigest()


class CampaignChangeDetector:
    """Compare campaign content with the last installed/published baseline."""

    def __init__(self, installation_store: Optional[InstallationStateStore] = None) -> None:
        self.installation_store = installation_store or InstallationStateStore()

    @staticmethod
    def installation_key(campaign_root: Path) -> str:
        return str(Path(campaign_root).expanduser().resolve())

    def persist_baseline(
        self, campaign_root: Path, fingerprint: Optional[str] = None, *, database_path: Optional[Path] = None
    ) -> str:
        value = fingerprint or calculate_campaign_fingerprint(campaign_root, database_path=database_path)
        if len(value) != 64:
            raise ValueError("campaign fingerprint must be a SHA-256 hexadecimal digest")
        try:
            bytes.fromhex(value)
        except ValueError as exc:
            raise ValueError("campaign fingerprint must be a SHA-256 hexadecimal digest") from exc
        self.installation_store.update_campaign_state(
            self.installation_key(campaign_root), baseline_fingerprint=value
        )
        return value

    def detect(self, campaign_root: Path, *, database_path: Optional[Path] = None) -> CampaignChangeResult:
        baseline = self.installation_store.campaign_state(
            self.installation_key(campaign_root)
        ).get("baseline_fingerprint")
        if not isinstance(baseline, str) or len(baseline) != 64:
            return CampaignChangeResult(CampaignChangeState.UNKNOWN)
        try:
            current = calculate_campaign_fingerprint(campaign_root, database_path=database_path)
        # Fingerprinting is a safety gate.  An unexpected implementation or
        # filesystem failure must fail closed instead of enabling replacement.
        except Exception as exc:
            return CampaignChangeResult(
                CampaignChangeState.UNKNOWN, baseline_fingerprint=baseline, error=str(exc)
            )
        state = (
            CampaignChangeState.CLEAN
            if current == baseline
            else CampaignChangeState.LOCALLY_MODIFIED
        )
        return CampaignChangeResult(state, current, baseline)


__all__ = [
    "CampaignChangeDetector", "CampaignChangeResult", "CampaignChangeState",
    "calculate_campaign_fingerprint", "create_campaign_backup_archive",
    "sqlite_snapshot_sha256",
]
