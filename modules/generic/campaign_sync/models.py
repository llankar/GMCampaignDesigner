"""Typed data exchanged by campaign synchronization components."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, Optional
from uuid import UUID


def _valid_uuid(value: str) -> str:
    return str(UUID(str(value)))


def _valid_sha256(value: str) -> str:
    normalized = str(value).lower()
    if len(normalized) != 64 or any(character not in "0123456789abcdef" for character in normalized):
        raise ValueError("snapshot_sha256 must be a 64-character hexadecimal digest")
    return normalized


def _validate_revision(revision: int, parent_revision: Optional[int]) -> None:
    if isinstance(revision, bool) or revision < 1:
        raise ValueError("revision must be a positive integer")
    if parent_revision is not None and (
        isinstance(parent_revision, bool) or not 0 <= parent_revision < revision
    ):
        raise ValueError("parent_revision must precede revision")


@dataclass(frozen=True)
class CampaignSyncMetadata:
    """Shared, campaign-local synchronization metadata."""

    campaign_id: str
    revision: int
    parent_revision: Optional[int]
    snapshot_sha256: str
    published_at: str
    publisher_installation_id: str
    bundle_version: int
    change_summary: Optional[str] = None
    snapshot_mode: str = "full_campaign"

    def __post_init__(self) -> None:
        object.__setattr__(self, "campaign_id", _valid_uuid(self.campaign_id))
        object.__setattr__(self, "snapshot_sha256", _valid_sha256(self.snapshot_sha256))
        _validate_revision(self.revision, self.parent_revision)

    def to_dict(self) -> Dict[str, Any]:
        return {key: value for key, value in asdict(self).items() if value is not None}

    @classmethod
    def from_dict(cls, value: Dict[str, Any]) -> "CampaignSyncMetadata":
        return cls(
            campaign_id=str(value["campaign_id"]),
            revision=int(value["revision"]),
            parent_revision=(int(value["parent_revision"]) if value.get("parent_revision") is not None else None),
            snapshot_sha256=str(value.get("snapshot_sha256") or ""),
            published_at=str(value.get("published_at") or ""),
            publisher_installation_id=str(value.get("publisher_installation_id") or ""),
            bundle_version=int(value.get("bundle_version") or 0),
            change_summary=(str(value["change_summary"]) if value.get("change_summary") is not None else None),
            snapshot_mode=str(value.get("snapshot_mode") or "full_campaign"),
        )


@dataclass(frozen=True)
class RemoteCampaignRevision:
    """Revision information discoverable from release metadata alone."""

    campaign_id: str
    revision: int
    parent_revision: Optional[int]
    snapshot_sha256: str
    snapshot_mode: str
    published_at: Optional[str] = None
    change_summary: Optional[str] = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "campaign_id", _valid_uuid(self.campaign_id))
        object.__setattr__(self, "snapshot_sha256", _valid_sha256(self.snapshot_sha256))
        _validate_revision(self.revision, self.parent_revision)

    @classmethod
    def from_dict(cls, value: Dict[str, Any]) -> "RemoteCampaignRevision":
        return cls(
            campaign_id=str(value["campaign_id"]),
            revision=int(value["revision"]),
            parent_revision=(int(value["parent_revision"]) if value.get("parent_revision") is not None else None),
            snapshot_sha256=str(value.get("snapshot_sha256") or ""),
            snapshot_mode=str(value.get("snapshot_mode") or "full_campaign"),
            published_at=(str(value["published_at"]) if value.get("published_at") else None),
            change_summary=(str(value["change_summary"]) if value.get("change_summary") else None),
        )
