"""Validation issue models shared across cross-entity validators."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Sequence


class IssueType(str, Enum):
    """Normalized issue types emitted by validation pipelines."""

    MISSING_REFERENCE = "MISSING_REFERENCE"
    AMBIGUOUS_REFERENCE = "AMBIGUOUS_REFERENCE"
    INVALID_HIERARCHY = "INVALID_HIERARCHY"


@dataclass(frozen=True)
class IssuePayload:
    """Structured payload used to surface validation issues in UI/logs."""

    source_entity: str
    field: str
    referenced_name: str
    expected_type: str
    candidates: Sequence[str] = field(default_factory=tuple)
    hierarchy_path: Sequence[str] = field(default_factory=tuple)


@dataclass(frozen=True)
class ValidationIssue:
    """Top-level issue object carrying type + payload."""

    issue_type: IssueType
    payload: IssuePayload
