"""Safe publication of versioned, complete campaign snapshots.

Manual gallery bundles intentionally remain in ``cross_campaign_asset_library``.
This module is the only route that may advance synchronized campaign state.
"""

from __future__ import annotations

import shutil
import sqlite3
import tempfile
import time
import json
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Callable, Optional
from uuid import uuid4

from modules.generic.cross_campaign_asset_service import (
    BUNDLE_VERSION,
    CampaignDatabase,
    export_bundle,
)

from .change_detector import CampaignChangeDetector, calculate_campaign_fingerprint
from .hashing import sha256_file
from .metadata_store import CampaignSyncMetadataStore, InstallationStateStore
from .models import CampaignSyncMetadata
from .delta_builder import build_inventory, write_delta_bundle


class CampaignPublishError(RuntimeError):
    """Base class for synchronization publication failures."""


class CampaignNotLinkedError(CampaignPublishError):
    """Raised when publication is requested for a legacy/unlinked campaign."""


class StaleParentError(CampaignPublishError):
    """The remote campaign advanced since this local snapshot was installed."""


class PublishOutcome(str, Enum):
    PUBLISHED = "published"
    CONFLICTED = "conflicted"


@dataclass(frozen=True)
class CampaignPublishResult:
    outcome: PublishOutcome
    revision: int
    campaign_id: str
    snapshot_sha256: str
    release: object
    conflict_message: Optional[str] = None

    @property
    def conflicted(self) -> bool:
        return self.outcome is PublishOutcome.CONFLICTED


class CampaignPublisher:
    """Publish full snapshots with optimistic revision checks.

    GitHub Releases has no compare-and-swap operation.  The checks immediately
    before and after release creation narrow, but cannot eliminate, a race
    between independent publishers.
    """

    def __init__(
        self,
        gallery_client,
        *,
        installation_store: Optional[InstallationStateStore] = None,
        retry_attempts: int = 3,
        retry_delay: float = 0.05,
        sleeper: Callable[[float], None] = time.sleep,
        checkpoint_interval: int = 10,
    ) -> None:
        self.gallery_client = gallery_client
        self.installation_store = installation_store or InstallationStateStore()
        self.retry_attempts = max(1, int(retry_attempts))
        self.retry_delay = max(0.0, float(retry_delay))
        self.sleeper = sleeper
        self.checkpoint_interval = max(2, int(checkpoint_interval))

    def enable(self, campaign_root: Path, *, database_path: Optional[Path] = None) -> CampaignSyncMetadata:
        """Give a legacy campaign a durable UUID and initial revision.

        The metadata lives inside the campaign and is therefore retained when
        the snapshot is installed on another computer.
        """
        root = Path(campaign_root).resolve()
        store = CampaignSyncMetadataStore(root)
        existing = store.read()
        if existing is not None:
            return existing
        fingerprint = calculate_campaign_fingerprint(root, database_path=database_path)
        metadata = CampaignSyncMetadata(
            campaign_id=str(uuid4()), revision=1, parent_revision=None,
            snapshot_sha256=fingerprint, published_at="",
            publisher_installation_id=self.installation_store.installation_id(),
            bundle_version=BUNDLE_VERSION, snapshot_mode="full_campaign",
        )
        store.write(metadata)
        CampaignChangeDetector(self.installation_store).persist_baseline(
            root, fingerprint, database_path=database_path
        )
        if database_path:
            inventory = build_inventory(root, Path(database_path))
            self.installation_store.update_campaign_state(
                str(root), baseline_inventory=[entry.__dict__ for entry in inventory]
            )
        return metadata

    def unlink(self, campaign_root: Path) -> bool:
        """Remove the shared link and machine-local baseline from this copy."""
        root = Path(campaign_root).resolve()
        store = CampaignSyncMetadataStore(root)
        existed = store.path.exists()
        store.path.unlink(missing_ok=True)
        state = self.installation_store.read()
        campaigns = state.get("campaign_sync")
        if isinstance(campaigns, dict):
            campaigns.pop(str(root), None)
            self.installation_store.write(state)
        return existed

    def publish(
        self,
        campaign_root: Path,
        *,
        database_path: Optional[Path] = None,
        title: Optional[str] = None,
        description: str = "",
        change_summary: Optional[str] = None,
        progress_callback=None,
    ) -> CampaignPublishResult:
        root = Path(campaign_root).resolve()
        local = CampaignSyncMetadataStore(root).read()
        if local is None:
            raise CampaignNotLinkedError(
                "Enable synchronization before publishing this campaign."
            )
        database = self._database_path(root, database_path)
        remote = self._retry(lambda: self.gallery_client.highest_revision(local.campaign_id))
        remote_revision = self._revision(remote)
        # A newly enabled revision 1 is an unpublished baseline.  Otherwise the
        # installed revision is the parent on which local edits are based.
        expected_parent = 0 if local.revision == 1 and not local.published_at else local.revision
        if remote_revision != expected_parent:
            raise StaleParentError(
                f"Remote revision is {remote_revision}; this local copy is based on "
                f"revision {expected_parent}. Download and reconcile the remote update first."
            )

        revision = remote_revision + 1
        temp_dir = Path(tempfile.mkdtemp(prefix="campaign_sync_publish_"))
        try:
            # Use one SQLite backup for record extraction, the archived database,
            # and the content digest.  Reading the live database independently
            # for each of those steps could describe different transactions.
            database_snapshot = temp_dir / database.name
            self._create_database_snapshot(database, database_snapshot)
            content_digest = calculate_campaign_fingerprint(
                root,
                database_path=database,
                database_snapshot_path=database_snapshot,
            )
            published_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            state = self.installation_store.campaign_state(str(root))
            from .delta_manifest import InventoryEntry
            try:
                baseline_inventory = tuple(InventoryEntry.from_dict(x) for x in state.get("baseline_inventory", ()))
            except (KeyError, TypeError, ValueError):
                baseline_inventory = ()
            current_inventory = build_inventory(root, database, database_snapshot_path=database_snapshot)
            is_checkpoint = revision == 1 or revision % self.checkpoint_interval == 0 or not baseline_inventory
            snapshot_mode = "full_campaign" if is_checkpoint else "campaign_delta"
            base_fingerprint = state.get("baseline_fingerprint") if snapshot_mode == "campaign_delta" else None
            metadata = CampaignSyncMetadata(
                campaign_id=local.campaign_id, revision=revision,
                parent_revision=(remote_revision or None), snapshot_sha256=content_digest,
                published_at=published_at,
                publisher_installation_id=self.installation_store.installation_id(),
                bundle_version=BUNDLE_VERSION, change_summary=change_summary,
                snapshot_mode=snapshot_mode,
                base_revision=remote_revision if snapshot_mode == "campaign_delta" else None,
                base_content_fingerprint=base_fingerprint,
            )
            archive = temp_dir / f"{root.name}-r{revision}.zip"
            if snapshot_mode == "campaign_delta":
                manifest = write_delta_bundle(
                    archive, root, database_snapshot, database.relative_to(root).as_posix(),
                    metadata.to_dict(), remote_revision, str(base_fingerprint),
                    baseline_inventory, current_inventory,
                )
            else:
                manifest = export_bundle(
                    archive, CampaignDatabase(root.name, root, database_snapshot), {},
                    include_database=True, include_systems=True,
                    sync_metadata=metadata, change_summary=change_summary,
                    progress_callback=progress_callback,
                )
                manifest["content_inventory"] = [entry.__dict__ for entry in current_inventory]
                self._replace_archive_manifest(archive, manifest)
            # The updater authenticates the downloaded ZIP against release
            # metadata.  Keep the content digest embedded in the ZIP manifest,
            # then publish/store the digest of the completed immutable archive.
            # (A ZIP cannot embed its own hash without making that hash stale.)
            digest = sha256_file(archive)
            release_sync = dict(manifest["sync"])
            release_sync["content_sha256"] = content_digest
            release_sync["snapshot_sha256"] = digest
            manifest["sync"] = release_sync
            metadata = CampaignSyncMetadata(
                campaign_id=metadata.campaign_id,
                revision=metadata.revision,
                parent_revision=metadata.parent_revision,
                snapshot_sha256=digest,
                published_at=metadata.published_at,
                publisher_installation_id=metadata.publisher_installation_id,
                bundle_version=metadata.bundle_version,
                change_summary=metadata.change_summary,
                snapshot_mode=metadata.snapshot_mode,
                base_revision=metadata.base_revision,
                base_content_fingerprint=metadata.base_content_fingerprint,
            )

            # GitHub has no compare-and-swap primitive, so make the second
            # optimistic check as close as possible to release creation.
            latest = self._retry(
                lambda: self.gallery_client.highest_revision(local.campaign_id)
            )
            if self._revision(latest) != remote_revision:
                raise StaleParentError(
                    "The remote campaign changed while preparing the snapshot; "
                    "retry after updating."
                )
            release = self.gallery_client.publish_bundle(
                archive, manifest, title=title or root.name,
                description=description, progress_callback=progress_callback,
            )
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

        matches = self._matching_revisions(local.campaign_id, revision)
        highest = self._retry(lambda: self.gallery_client.highest_revision(local.campaign_id))
        duplicate = len(matches) > 1 or self._revision(highest) != revision
        if duplicate:
            return CampaignPublishResult(
                PublishOutcome.CONFLICTED, revision, local.campaign_id, digest, release,
                "A duplicate or newer revision was detected after publication. Reconcile manually; no local baseline was advanced.",
            )

        # Release and verification succeeded: only now advance installed state.
        CampaignSyncMetadataStore(root).write(metadata)
        CampaignChangeDetector(self.installation_store).persist_baseline(
            root, content_digest, database_path=database
        )
        self.installation_store.update_campaign_state(
            str(root), installed_revision=revision,
            baseline_inventory=[entry.__dict__ for entry in current_inventory],
        )
        return CampaignPublishResult(
            PublishOutcome.PUBLISHED, revision, local.campaign_id, digest, release
        )

    @staticmethod
    def _create_database_snapshot(source_path: Path, destination_path: Path) -> None:
        source = sqlite3.connect(
            f"file:{source_path.resolve().as_posix()}?mode=ro", uri=True
        )
        destination = sqlite3.connect(str(destination_path))
        try:
            source.backup(destination)
        finally:
            destination.close()
            source.close()

    @staticmethod
    def _replace_archive_manifest(archive: Path, manifest: dict) -> None:
        """Rewrite the generated ZIP so inventory is part of the immutable revision."""
        replacement = archive.with_suffix(".rewritten.zip")
        with zipfile.ZipFile(archive, "r") as source, zipfile.ZipFile(
            replacement, "w", compression=zipfile.ZIP_DEFLATED
        ) as destination:
            for info in source.infolist():
                if info.filename != "manifest.json":
                    destination.writestr(info, source.read(info.filename))
            destination.writestr("manifest.json", json.dumps(manifest, indent=2, ensure_ascii=False))
        replacement.replace(archive)

    def _matching_revisions(self, campaign_id: str, revision: int) -> list[object]:
        list_bundles = getattr(self.gallery_client, "list_bundles", None)
        if not callable(list_bundles):
            return []
        bundles = self._retry(list_bundles)
        return [
            item for item in bundles
            if getattr(item, "campaign_id", None) == campaign_id
            and getattr(item, "revision", None) == revision
        ]

    def _retry(self, operation):
        for attempt in range(self.retry_attempts):
            try:
                return operation()
            except Exception:
                if attempt + 1 >= self.retry_attempts:
                    raise
                self.sleeper(self.retry_delay * (2 ** attempt))

    @staticmethod
    def _revision(remote: object | None) -> int:
        value = getattr(remote, "revision", 0) if remote is not None else 0
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise CampaignPublishError("Remote campaign has invalid revision metadata")
        return value

    @staticmethod
    def _database_path(root: Path, value: Optional[Path]) -> Path:
        if value is not None:
            path = Path(value).resolve()
        else:
            candidates = list(root.glob("*.db"))
            if len(candidates) != 1:
                raise CampaignPublishError(f"Expected one campaign database, found {len(candidates)}")
            path = candidates[0].resolve()
        if not path.is_file() or root not in path.parents:
            raise CampaignPublishError("Campaign database must be inside the campaign directory")
        return path


__all__ = [
    "CampaignNotLinkedError", "CampaignPublishError", "CampaignPublishResult",
    "CampaignPublisher", "PublishOutcome", "StaleParentError",
]
