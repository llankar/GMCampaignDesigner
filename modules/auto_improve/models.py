"""Data models for auto improve."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List


@dataclass(frozen=True)
class ImprovementProposal:
    slug: str
    title: str
    summary: str
    scope: str
    prompt: str


@dataclass
class ExecutionReport:
    proposal: ImprovementProposal
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None
    steps: List[str] = field(default_factory=list)
    success: bool = False

    def add_step(self, message: str) -> None:
        """Handle add step."""
        self.steps.append(message)
