"""Transactional installation of complete synchronized campaign snapshots.

This module deliberately does not use ``cross_campaign_asset_service.apply_import``.
That function is a merge-oriented, manual import facility; synchronization must
replace the complete snapshot so that remote deletions remain deletions.
"""

from __future__ import annotations

import configparser
import json
import os
import shutil
import sqlite3
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable, Optional

from modules.generic.cross_campaign_asset_service import (
    BUNDLE_VERSION,
    _safe_extract_zip,
)
from modules.helpers import backup_helper

from .change_detector import CampaignChangeDetector, calculate_campaign_fingerprint
from .hashing import sha256_file
from .metadata_store import CampaignSyncMetadataStore, InstallationStateStore
from .models import CampaignSyncMetadata
from .delta_applier import apply_delta, clone_campaign
from .delta_builder import build_inventory
from .delta_manifest import DeltaManifest, InventoryEntry

ProgressCallback = Callable[[str, float], None]
CancelCallback = Callable[[], bool]
LifecycleCallback = Callable[[], None]


class CampaignUpdateError(RuntimeError):
    """The synchronized snapshot could not be installed safely."""


class CampaignUpdateCancelled(CampaignUpdateError):
    """Cancellation requested before the replacement transaction began."""


@dataclass(frozen=True)
class CampaignUpdateReceipt:
    campaign_root: Path
    revision: int
    backup_path: Path
    baseline_fingerprint: str


def _noop() -> None:
    return None


def _manifest_path(root: Path, value: object, *, label: str) -> Path:
    text = str(value or "").replace("\\", "/")
    candidate = (root / text).resolve()
    if not text or Path(text).is_absolute():
        raise CampaignUpdateError(f"Invalid {label} path: {text!r}")
    try:
        candidate.relative_to(root.resolve())
    except ValueError as exc:
        raise CampaignUpdateError(f"Invalid {label} path: {text!r}") from exc
    return candidate


def _iter_declared_files(manifest: dict) -> Iterable[tuple[str, dict]]:
    database = manifest.get("database")
    if isinstance(database, dict):
        yield str(database.get("relative_path") or ""), database
    for meta in (manifest.get("entities") or {}).values():
        if isinstance(meta, dict):
            yield str(meta.get("data_path") or ""), meta
    for key in ("systems", "world_maps"):
        meta = manifest.get(key)
        if isinstance(meta, dict):
            yield str(meta.get("data_path") or meta.get("path") or ""), meta
    for key in ("assets", "extra_files"):
        for meta in manifest.get(key) or ():
            if isinstance(meta, dict):
                yield str(meta.get("bundle_path") or ""), meta


def _validate_declared_hashes(extracted: Path, manifest: dict) -> None:
    """Validate every manifest entry that declares a SHA-256 digest."""
    for relative, meta in _iter_declared_files(manifest):
        expected = meta.get("sha256") or meta.get("checksum_sha256")
        if not expected:
            continue
        path = _manifest_path(extracted, relative, label="declared file")
        if not path.is_file():
            raise CampaignUpdateError(f"Declared bundle file is missing: {relative}")
        if sha256_file(path).lower() != str(expected).lower():
            raise CampaignUpdateError(f"SHA-256 mismatch for bundle file: {relative}")


def _copy_payload(extracted: Path, staging: Path, manifest: dict) -> Path:
    """Materialize the full-bundle transport layout as a campaign directory."""
    database = manifest["database"]
    source_db = _manifest_path(
        extracted, database.get("relative_path"), label="database"
    )
    if not source_db.is_file():
        raise CampaignUpdateError("Bundle database entry does not exist")
    db_name = str(database.get("file_name") or source_db.name)
    if Path(db_name).name != db_name:
        raise CampaignUpdateError("Invalid database file name")
    staging.mkdir()
    target_db = staging / db_name
    shutil.copy2(source_db, target_db)

    for entry in manifest.get("assets") or ():
        if not isinstance(entry, dict):
            continue
        source = _manifest_path(extracted, entry.get("bundle_path"), label="asset")
        destination = _manifest_path(
            staging, entry.get("original_path"), label="asset destination"
        )
        if source.is_file():
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
    for entry in manifest.get("extra_files") or ():
        if not isinstance(entry, dict):
            continue
        source = _manifest_path(extracted, entry.get("bundle_path"), label="extra file")
        destination = _manifest_path(
            staging, entry.get("relative_path"), label="extra destination"
        )
        if not source.is_file():
            raise CampaignUpdateError(f"Declared extra file is missing: {source.name}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    return target_db


def _validate_sqlite(path: Path) -> None:
    try:
        connection = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
        try:
            result = connection.execute("PRAGMA quick_check").fetchone()
        finally:
            connection.close()
    except sqlite3.Error as exc:
        raise CampaignUpdateError(
            f"Unable to open bundled campaign database: {exc}"
        ) from exc
    if not result or result[0] != "ok":
        raise CampaignUpdateError("Bundled campaign database failed SQLite validation")


def _preserve_local_settings(
    active: Path, staging: Path, relative_paths: Iterable[Path]
) -> None:
    """Copy only explicitly documented local files, filtering Gallery secrets."""
    for relative in relative_paths:
        relative = Path(relative)
        if relative.is_absolute() or ".." in relative.parts:
            raise CampaignUpdateError(
                f"Invalid machine-local settings path: {relative}"
            )
        source, destination = active / relative, staging / relative
        if not source.is_file():
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        # Delta staging may use hard links. Detach before filtering or copying
        # so staging can never mutate the still-active campaign.
        destination.unlink(missing_ok=True)
        if source.name.lower() == "settings.ini":
            parser = configparser.ConfigParser()
            parser.read(source, encoding="utf-8")
            if parser.has_section("Gallery"):
                for option in tuple(parser.options("Gallery")):
                    if "token" in option.lower() or "credential" in option.lower():
                        parser.remove_option("Gallery", option)
            with destination.open("w", encoding="utf-8") as handle:
                parser.write(handle)
        else:
            shutil.copy2(source, destination)


class CampaignUpdater:
    """Download, validate, and atomically replace one active campaign."""

    def __init__(
        self,
        gallery_client,
        *,
        installation_store: Optional[InstallationStateStore] = None,
        backup_creator: Optional[Callable[[Path], object]] = None,
        quiesce: LifecycleCallback = _noop,
        reopen: LifecycleCallback = _noop,
        local_settings: Iterable[Path] = (),
        replace: Callable[[os.PathLike, os.PathLike], None] = os.replace,
    ) -> None:
        self.gallery_client = gallery_client
        self.installation_store = installation_store or InstallationStateStore()
        self.backup_creator = backup_creator or backup_helper.create_backup_archive
        self.quiesce = quiesce
        self.reopen = reopen
        self.local_settings = tuple(local_settings)
        self.replace = replace

    def install(
        self,
        campaign_root: Path,
        release,
        *,
        progress: Optional[ProgressCallback] = None,
        cancelled: Optional[CancelCallback] = None,
    ) -> CampaignUpdateReceipt:
        active = Path(campaign_root).expanduser().resolve()
        current = CampaignSyncMetadataStore(active).read()
        if current is None:
            raise CampaignUpdateError("Campaign is not linked for synchronization")
        expected_mode = str(getattr(release, "snapshot_mode", "") or "").lower()
        if expected_mode and expected_mode not in {"full_campaign", "campaign_delta"}:
            raise CampaignUpdateError(
                "Asset-only bundles cannot be synchronized automatically"
            )

        def report(message: str, fraction: float) -> None:
            if progress:
                progress(message, fraction)

        def check_cancel() -> None:
            if cancelled and cancelled():
                raise CampaignUpdateCancelled("Campaign update cancelled")

        parent = active.parent
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        backup = parent / f"{active.name}.backup-{stamp}.zip"
        rollback = parent / f".{active.name}.rollback-{stamp}"
        staging = parent / f".{active.name}.staging-{stamp}"
        replacement_started = False
        with tempfile.TemporaryDirectory(prefix="gmcd_sync_download_") as temp_name:
            archive = Path(temp_name) / "campaign.zip"
            check_cancel()
            report("Downloading campaign snapshot…", 0.05)
            self.gallery_client.download_bundle(
                release, archive, progress_callback=progress
            )
            check_cancel()
            expected_archive_hash = str(
                getattr(release, "snapshot_sha256", "") or ""
            ).lower()
            if (
                not expected_archive_hash
                or sha256_file(archive) != expected_archive_hash
            ):
                raise CampaignUpdateError(
                    "Downloaded archive SHA-256 does not match release metadata"
                )

            extracted = Path(temp_name) / "extracted"
            extracted.mkdir()
            try:
                with zipfile.ZipFile(archive) as bundle:
                    _safe_extract_zip(bundle, extracted)
            except (zipfile.BadZipFile, ValueError) as exc:
                raise CampaignUpdateError(f"Invalid campaign ZIP: {exc}") from exc
            manifest_path = extracted / "manifest.json"
            if not manifest_path.is_file():
                raise CampaignUpdateError("Bundle manifest missing")
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if manifest.get("version") != BUNDLE_VERSION:
                raise CampaignUpdateError(
                    f"Unsupported bundle version: {manifest.get('version')}"
                )
            bundle_mode = manifest.get("bundle_mode")
            if bundle_mode not in {"full_campaign", "campaign_delta"} or not isinstance(manifest.get("database"), dict):
                raise CampaignUpdateError(
                    "Asset-only bundles cannot be synchronized automatically"
                )
            sync = CampaignSyncMetadata.from_dict(manifest.get("sync") or {})
            if sync.snapshot_mode != bundle_mode:
                raise CampaignUpdateError("Bundle mode does not match synchronization metadata")
            if expected_mode and expected_mode != bundle_mode:
                raise CampaignUpdateError("Selected release mode does not match the downloaded bundle")
            if sync.bundle_version != BUNDLE_VERSION:
                raise CampaignUpdateError("Incompatible synchronized bundle version")
            release_campaign = str(
                getattr(release, "campaign_id", "") or sync.campaign_id
            )
            release_revision = getattr(release, "revision", sync.revision)
            release_parent = getattr(release, "parent_revision", sync.parent_revision)
            if (
                sync.campaign_id != current.campaign_id
                or release_campaign != current.campaign_id
            ):
                raise CampaignUpdateError(
                    "Campaign ID does not match the active campaign"
                )
            if sync.revision != release_revision or sync.revision <= current.revision:
                raise CampaignUpdateError(
                    "Bundle revision does not match the selected release"
                )
            if bundle_mode == "campaign_delta" and (
                sync.parent_revision != current.revision or release_parent != current.revision
            ):
                raise CampaignUpdateError(
                    "Bundle parent revision does not match the installed revision"
                )
            delta = None
            if bundle_mode == "campaign_delta":
                try:
                    delta = DeltaManifest.from_dict(manifest.get("delta") or {})
                except (KeyError, TypeError, ValueError) as exc:
                    raise CampaignUpdateError(f"Invalid delta manifest: {exc}") from exc
                baseline = self.installation_store.campaign_state(str(active)).get("baseline_fingerprint")
                if (
                    sync.base_revision != current.revision
                    or delta.base_revision != current.revision
                    or sync.base_content_fingerprint != baseline
                    or delta.base_content_fingerprint != baseline
                ):
                    raise CampaignUpdateError(
                        "Delta base revision or content fingerprint does not match the installed campaign"
                    )
            _validate_declared_hashes(extracted, manifest)
            check_cancel()
            report("Creating safety backup…", 0.55)
            try:
                self.backup_creator(backup)
            except Exception as exc:
                raise CampaignUpdateError(
                    f"Unable to create campaign backup: {exc}"
                ) from exc
            check_cancel()
            if staging.exists() or rollback.exists():
                raise CampaignUpdateError("Update staging location already exists")
            if delta is None:
                target_db = _copy_payload(extracted, staging, manifest)
            else:
                clone_campaign(active, staging)
                try:
                    target_db = apply_delta(extracted, staging, delta, manifest["database"])
                except ValueError as exc:
                    raise CampaignUpdateError(str(exc)) from exc
            _validate_sqlite(target_db)
            _preserve_local_settings(active, staging, self.local_settings)
            try:
                inventory_data = (
                    delta.inventory if delta is not None else
                    tuple(InventoryEntry.from_dict(item) for item in manifest.get("content_inventory", ()))
                )
            except (KeyError, TypeError, ValueError) as exc:
                raise CampaignUpdateError(f"Invalid content inventory: {exc}") from exc
            if inventory_data:
                actual_inventory = build_inventory(staging, target_db, database_snapshot_path=target_db)
                if actual_inventory != inventory_data:
                    raise CampaignUpdateError("Reconstructed campaign inventory does not match the publisher")
            expected_content = str((manifest.get("sync") or {}).get("snapshot_sha256") or "")
            staged_fingerprint = calculate_campaign_fingerprint(
                staging, database_path=target_db, database_snapshot_path=target_db
            )
            # Legacy full bundles did not carry an inventory and used this
            # field only for transport metadata. New versioned snapshots do,
            # and can therefore enforce publisher/reconstruction identity.
            if inventory_data and staged_fingerprint != expected_content:
                raise CampaignUpdateError(
                    "Reconstructed campaign fingerprint does not match the publisher"
                )
            CampaignSyncMetadataStore(staging).write(sync)
            check_cancel()
            report("Preparing campaign replacement…", 0.9)
            self.quiesce()
            replacement_started = True
            try:
                self.replace(active, rollback)
                try:
                    self.replace(staging, active)
                except Exception:
                    self.replace(rollback, active)
                    raise
                try:
                    self.reopen()
                    baseline = staged_fingerprint
                    CampaignChangeDetector(self.installation_store).persist_baseline(
                        active, baseline, database_path=active / target_db.name
                    )
                    self.installation_store.update_campaign_state(
                        str(active), installed_revision=sync.revision,
                        baseline_inventory=[entry.__dict__ for entry in inventory_data],
                    )
                except Exception as exc:
                    failed = parent / f".{active.name}.failed-{stamp}"
                    self.replace(active, failed)
                    self.replace(rollback, active)
                    try:
                        self.reopen()
                    finally:
                        shutil.rmtree(failed, ignore_errors=True)
                    raise CampaignUpdateError(
                        f"Campaign reopen failed; previous campaign restored: {exc}"
                    ) from exc
                shutil.rmtree(rollback)
                return CampaignUpdateReceipt(active, sync.revision, backup, baseline)
            except CampaignUpdateError:
                raise
            except Exception as exc:
                if rollback.exists() and not active.exists():
                    self.replace(rollback, active)
                    try:
                        self.reopen()
                    except Exception:
                        pass
                elif active.exists():
                    # The first rename can fail after the lifecycle was
                    # quiesced; resume the untouched campaign in that case.
                    try:
                        self.reopen()
                    except Exception:
                        pass
                raise CampaignUpdateError(
                    f"Atomic campaign replacement failed: {exc}"
                ) from exc
            finally:
                if staging.exists():
                    shutil.rmtree(staging, ignore_errors=True)
                # No progress/cancellation callbacks are consulted after
                # replacement_started becomes true: commit or rollback only.
                _ = replacement_started

    def install_chain(self, campaign_root: Path, releases: Iterable[object], **kwargs) -> list[CampaignUpdateReceipt]:
        """Install a strictly ordered compatible chain, never skipping a delta base."""
        ordered = sorted(releases, key=lambda item: getattr(item, "revision", 0))
        receipts: list[CampaignUpdateReceipt] = []
        for release in ordered:
            current = CampaignSyncMetadataStore(campaign_root).read()
            if current is None:
                raise CampaignUpdateError("Campaign is not linked for synchronization")
            revision = getattr(release, "revision", None)
            if revision <= current.revision:
                continue
            mode = str(getattr(release, "snapshot_mode", "full_campaign"))
            base = getattr(release, "base_revision", getattr(release, "parent_revision", None))
            if mode == "campaign_delta" and base != current.revision:
                raise CampaignUpdateError("Delta chain is incomplete or based on an unrelated revision")
            receipts.append(self.install(campaign_root, release, **kwargs))
        return receipts


__all__ = [
    "CampaignUpdateCancelled",
    "CampaignUpdateError",
    "CampaignUpdateReceipt",
    "CampaignUpdater",
]
