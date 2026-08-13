"""Immutable values shared by the automatic publication components."""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from enum import Enum
from pathlib import Path
from typing import Any, Mapping, Optional


class SyncState(str, Enum):
    UNSAVED = "Unsaved changes"
    WAITING = "Waiting to publish"
    QUEUED = "Queued"
    PREPARING = "Preparing"
    UPLOADING = "Uploading"
    FURTHER_CHANGES = "Further changes pending"
    SYNCHRONIZED = "Synchronized"
    OFFLINE = "Offline"
    RETRY_SCHEDULED = "Retry scheduled"
    AUTH_REQUIRED = "Authentication required"
    FAILED = "Failed"
    CONFLICT = "Conflict"


class EventKind(str, Enum):
    STATE = "state"
    PROGRESS = "progress"
    SUCCESS = "success"
    FAILURE = "failure"
    CONFLICT = "conflict"


@dataclass(frozen=True)
class PublicationJob:
    job_id: str
    campaign_id: str
    campaign_name: str
    campaign_root: Path
    database_path: Path
    expected_parent_revision: int
    first_dirty_at: float
    last_dirty_at: float
    title: str
    summary: str
    fingerprint: Optional[str] = None
    force_full_checkpoint: bool = False


@dataclass(frozen=True)
class OutboxEntry:
    campaign_id: str
    campaign_name: str
    campaign_root: Path
    database_path: Path
    expected_parent_revision: int
    first_dirty_at: float
    last_dirty_at: float
    retry_count: int = 0
    next_attempt_at: float = 0.0
    failure_category: Optional[str] = None
    failure_message: Optional[str] = None
    force_full_checkpoint: bool = False

    def updated(self, **changes: Any) -> "OutboxEntry":
        return replace(self, **changes)

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["campaign_root"] = str(self.campaign_root)
        value["database_path"] = str(self.database_path)
        return value

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "OutboxEntry":
        return cls(
            campaign_id=str(value["campaign_id"]),
            campaign_name=str(value.get("campaign_name") or value["campaign_id"]),
            campaign_root=Path(str(value["campaign_root"])).expanduser().resolve(),
            database_path=Path(str(value["database_path"])).expanduser().resolve(),
            expected_parent_revision=int(value["expected_parent_revision"]),
            first_dirty_at=float(value["first_dirty_at"]),
            last_dirty_at=float(value["last_dirty_at"]),
            retry_count=max(0, int(value.get("retry_count", 0))),
            next_attempt_at=max(0.0, float(value.get("next_attempt_at", 0))),
            failure_category=value.get("failure_category") or None,
            failure_message=value.get("failure_message") or None,
            force_full_checkpoint=bool(value.get("force_full_checkpoint", False)),
        )


@dataclass(frozen=True)
class WorkerEvent:
    job_id: str
    campaign_id: str
    sequence: int
    kind: EventKind
    state: SyncState
    message: str = ""
    progress: Optional[float] = None
    result: Any = None
    failure_category: Optional[str] = None
    terminal: bool = False
