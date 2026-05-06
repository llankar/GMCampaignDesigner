"""In-memory store for validation issues ignored during the current session."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from src.validation import ValidationIssue


@dataclass(frozen=True, order=True)
class IgnoredIssueKey:
    """Stable, hashable key identifying one validation issue in this session."""

    issue_type: str
    source_entity: str
    source_type: str
    field: str
    referenced_name: str
    expected_type: str
    hierarchy_path: tuple[str, ...]


class SessionIgnoreStore:
    """Remember ignored issues in memory only.

    The store deliberately has no file path, serializer, or persistence hook.
    Creating a new instance starts a fresh session with no ignored issues.
    """

    def __init__(self) -> None:
        self._ignored: set[IgnoredIssueKey] = set()

    def ignore(self, issue: ValidationIssue) -> IgnoredIssueKey:
        """Mark an issue as ignored for the lifetime of this store instance."""

        key = issue_key(issue)
        self._ignored.add(key)
        return key

    def unignore(self, issue: ValidationIssue) -> bool:
        """Remove an issue from the ignored set.

        Returns ``True`` only when the issue was previously ignored.
        """

        key = issue_key(issue)
        if key not in self._ignored:
            return False
        self._ignored.remove(key)
        return True

    def is_ignored(self, issue: ValidationIssue) -> bool:
        """Return whether an issue is ignored in the current session."""

        return issue_key(issue) in self._ignored

    def visible_issues(self, issues: Iterable[ValidationIssue]) -> tuple[ValidationIssue, ...]:
        """Filter ignored issues from an iterable while preserving order."""

        return tuple(issue for issue in issues if not self.is_ignored(issue))

    def clear(self) -> None:
        """Forget all ignored issues for the current session."""

        self._ignored.clear()

    def __len__(self) -> int:
        return len(self._ignored)


def issue_key(issue: ValidationIssue) -> IgnoredIssueKey:
    """Create the canonical in-memory key for a validation issue."""

    payload = issue.payload
    return IgnoredIssueKey(
        issue_type=str(issue.issue_type.value),
        source_entity=payload.source_entity,
        source_type=payload.source_type,
        field=payload.field,
        referenced_name=payload.referenced_name,
        expected_type=payload.expected_type,
        hierarchy_path=tuple(str(part) for part in payload.hierarchy_path),
    )
