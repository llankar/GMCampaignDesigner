"""UI-independent update discovery for synchronized campaigns."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Callable, Optional

from .metadata_store import CampaignSyncMetadataStore, InstallationStateStore
from .change_detector import CampaignChangeDetector, CampaignChangeState


class UpdateStatus(str, Enum):
    UP_TO_DATE = "up_to_date"
    UPDATE_AVAILABLE = "update_available"
    OFFLINE = "offline"
    UNLINKED = "unlinked"
    REMOTE_INVALID = "remote_invalid"


@dataclass(frozen=True)
class UpdateCheckSettings:
    enabled: bool = True
    offline: bool = False
    interval_seconds: int = 24 * 60 * 60
    force: bool = False


@dataclass(frozen=True)
class CampaignUpdateResult:
    status: UpdateStatus
    campaign_name: str
    installed_revision: Optional[int] = None
    available_revision: Optional[int] = None
    published_at: Optional[datetime] = None
    publisher: Optional[str] = None
    change_summary: Optional[str] = None
    bundle: object | None = None
    checked_remote: bool = False
    ignored: bool = False
    error: Optional[str] = None
    local_change_state: CampaignChangeState = CampaignChangeState.UNKNOWN
    conflict: bool = False
    snapshot_mode: str = "full_campaign"
    transfer_size: Optional[int] = None
    required_base_revision: Optional[int] = None


class CampaignUpdateChecker:
    """Compare local and remote integer revisions without importing any UI code."""

    def __init__(
        self,
        gallery_client,
        *,
        installation_store: Optional[InstallationStateStore] = None,
        clock: Optional[Callable[[], datetime]] = None,
    ) -> None:
        self.gallery_client = gallery_client
        self.installation_store = installation_store or InstallationStateStore()
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    @staticmethod
    def installation_key(campaign_root: Path) -> str:
        return str(Path(campaign_root).expanduser().resolve())

    def check(
        self, campaign_root: Path, settings: UpdateCheckSettings = UpdateCheckSettings()
    ) -> CampaignUpdateResult:
        root = Path(campaign_root)
        name = root.name
        try:
            metadata = CampaignSyncMetadataStore(root).read()
        except (OSError, ValueError, KeyError, TypeError) as exc:
            return CampaignUpdateResult(UpdateStatus.REMOTE_INVALID, name, error=str(exc))
        if metadata is None or not metadata.campaign_id:
            return CampaignUpdateResult(UpdateStatus.UNLINKED, name)
        # Resolve campaign identity before applying connectivity preferences:
        # an unlinked campaign remains UNLINKED even while the application is
        # offline/disabled, and neither case ever reaches the gallery client.
        if not settings.enabled or settings.offline:
            return CampaignUpdateResult(
                UpdateStatus.OFFLINE, name, installed_revision=metadata.revision
            )

        key = self.installation_key(root)
        local_state = self.installation_store.campaign_state(key)
        now = self.clock()
        if not settings.force and not self._is_due(
            local_state.get("last_checked_at"), now, settings.interval_seconds
        ):
            return CampaignUpdateResult(
                UpdateStatus.UP_TO_DATE,
                name,
                installed_revision=metadata.revision,
                checked_remote=False,
            )

        try:
            remote = self.gallery_client.highest_revision(metadata.campaign_id)
        except Exception as exc:
            return CampaignUpdateResult(
                UpdateStatus.OFFLINE,
                name,
                installed_revision=metadata.revision,
                error=str(exc),
            )

        self.installation_store.update_campaign_state(
            key, last_checked_at=now.astimezone(timezone.utc).isoformat()
        )
        if remote is None:
            return CampaignUpdateResult(
                UpdateStatus.UP_TO_DATE, name, metadata.revision, checked_remote=True
            )
        revision = getattr(remote, "revision", None)
        if isinstance(revision, bool) or not isinstance(revision, int) or revision < 1:
            return CampaignUpdateResult(
                UpdateStatus.REMOTE_INVALID,
                name,
                installed_revision=metadata.revision,
                bundle=remote,
                checked_remote=True,
            )
        if str(getattr(remote, "campaign_id", "")) != metadata.campaign_id:
            return CampaignUpdateResult(
                UpdateStatus.REMOTE_INVALID,
                name,
                installed_revision=metadata.revision,
                bundle=remote,
                checked_remote=True,
            )

        ignored_revision = self._integer_or_none(local_state.get("ignored_revision"))
        available = revision > metadata.revision
        ignored = available and ignored_revision == revision
        status = UpdateStatus.UPDATE_AVAILABLE if available and not ignored else UpdateStatus.UP_TO_DATE
        local_changes = CampaignChangeDetector(self.installation_store).detect(root)
        remote_parent = getattr(remote, "parent_revision", None)
        if remote_parent is None:
            remote_metadata = getattr(remote, "metadata", {})
            sync_value = remote_metadata.get("sync", {}) if isinstance(remote_metadata, dict) else {}
            remote_parent = sync_value.get("parent_revision") if isinstance(sync_value, dict) else None
        conflict = (
            available
            and local_changes.state is CampaignChangeState.LOCALLY_MODIFIED
            and remote_parent == metadata.revision
        )
        summary = getattr(remote, "change_summary", None)
        if not summary:
            remote_metadata = getattr(remote, "metadata", {})
            sync = remote_metadata.get("sync", {}) if isinstance(remote_metadata, dict) else {}
            summary = sync.get("change_summary") if isinstance(sync, dict) else None
        return CampaignUpdateResult(
            status,
            name,
            installed_revision=metadata.revision,
            available_revision=revision,
            published_at=getattr(remote, "published_at", None),
            publisher=getattr(remote, "author", None) or None,
            change_summary=str(summary) if summary else None,
            bundle=remote,
            checked_remote=True,
            ignored=ignored,
            local_change_state=local_changes.state,
            conflict=conflict,
            snapshot_mode=str(getattr(remote, "snapshot_mode", "full_campaign")),
            transfer_size=getattr(remote, "transfer_size", None),
            required_base_revision=getattr(remote, "base_revision", None),
        )

    def ignore_revision(self, campaign_root: Path, revision: int) -> None:
        if isinstance(revision, bool) or not isinstance(revision, int) or revision < 1:
            raise ValueError("revision must be a positive integer")
        self.installation_store.update_campaign_state(
            self.installation_key(campaign_root), ignored_revision=revision
        )

    @staticmethod
    def _integer_or_none(value: object) -> Optional[int]:
        return value if isinstance(value, int) and not isinstance(value, bool) else None

    @staticmethod
    def _is_due(value: object, now: datetime, interval_seconds: int) -> bool:
        if not value or interval_seconds <= 0:
            return True
        try:
            checked = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            if checked.tzinfo is None:
                checked = checked.replace(tzinfo=timezone.utc)
            return (now - checked.astimezone(timezone.utc)).total_seconds() >= interval_seconds
        except (TypeError, ValueError):
            return True


__all__ = [
    "CampaignUpdateChecker",
    "CampaignUpdateResult",
    "UpdateCheckSettings",
    "UpdateStatus",
]
