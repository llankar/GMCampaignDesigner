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
    if isinstance(revision, bool) or not isinstance(revision, int) or revision < 1:
        raise ValueError("revision must be a positive integer")
    if parent_revision is not None and (
        isinstance(parent_revision, bool)
        or not isinstance(parent_revision, int)
        or not 0 <= parent_revision < revision
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
    base_revision: Optional[int] = None
    base_content_fingerprint: Optional[str] = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "campaign_id", _valid_uuid(self.campaign_id))
        object.__setattr__(self, "snapshot_sha256", _valid_sha256(self.snapshot_sha256))
        _validate_revision(self.revision, self.parent_revision)
        if self.snapshot_mode not in {"full_campaign", "campaign_delta"}:
            raise ValueError("snapshot_mode must be full_campaign or campaign_delta")
        if self.snapshot_mode == "campaign_delta":
            if self.base_revision != self.parent_revision or self.base_revision is None:
                raise ValueError("delta base_revision must equal parent_revision")
            if not self.base_content_fingerprint:
                raise ValueError("delta requires base_content_fingerprint")
            object.__setattr__(self, "base_content_fingerprint", _valid_sha256(self.base_content_fingerprint))

    def to_dict(self) -> Dict[str, Any]:
        return {key: value for key, value in asdict(self).items() if value is not None}

    @classmethod
    def from_dict(cls, value: Dict[str, Any]) -> "CampaignSyncMetadata":
        return cls(
            campaign_id=str(value["campaign_id"]),
            # Revisions are protocol integers.  Do not silently turn names,
            # numeric strings, floats, or booleans into valid revisions.
            revision=value["revision"],
            parent_revision=value.get("parent_revision"),
            snapshot_sha256=str(value.get("snapshot_sha256") or ""),
            published_at=str(value.get("published_at") or ""),
            publisher_installation_id=str(value.get("publisher_installation_id") or ""),
            bundle_version=int(value.get("bundle_version") or 0),
            change_summary=(str(value["change_summary"]) if value.get("change_summary") is not None else None),
            snapshot_mode=str(value.get("snapshot_mode") or "full_campaign"),
            base_revision=value.get("base_revision"),
            base_content_fingerprint=value.get("base_content_fingerprint"),
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
    base_revision: Optional[int] = None
    base_content_fingerprint: Optional[str] = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "campaign_id", _valid_uuid(self.campaign_id))
        object.__setattr__(self, "snapshot_sha256", _valid_sha256(self.snapshot_sha256))
        _validate_revision(self.revision, self.parent_revision)
        if self.snapshot_mode not in {"full_campaign", "campaign_delta"}:
            raise ValueError("snapshot_mode must be full_campaign or campaign_delta")
        if self.snapshot_mode == "campaign_delta":
            if self.base_revision != self.parent_revision or self.base_revision is None or not self.base_content_fingerprint:
                raise ValueError("delta release is missing its required base")
            object.__setattr__(self, "base_content_fingerprint", _valid_sha256(self.base_content_fingerprint))

    @classmethod
    def from_dict(cls, value: Dict[str, Any]) -> "RemoteCampaignRevision":
        return cls(
            campaign_id=str(value["campaign_id"]),
            revision=value["revision"],
            parent_revision=value.get("parent_revision"),
            snapshot_sha256=str(value.get("snapshot_sha256") or ""),
            snapshot_mode=str(value.get("snapshot_mode") or "full_campaign"),
            published_at=(str(value["published_at"]) if value.get("published_at") else None),
            change_summary=(str(value["change_summary"]) if value.get("change_summary") else None),
            base_revision=value.get("base_revision"),
            base_content_fingerprint=value.get("base_content_fingerprint"),
        )
