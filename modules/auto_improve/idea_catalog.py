"""Catalog helpers for auto improve idea."""
from __future__ import annotations

from pathlib import Path

from modules.auto_improve.catalog.idea_generation_service import IdeaGenerationService
from modules.auto_improve.command_runner import CommandRunner
from modules.auto_improve.models import ImprovementProposal

_SERVICE: IdeaGenerationService | None = None


def configure_catalog(runner: CommandRunner, command_template: str, workdir: Path) -> None:
    """Handle configure catalog."""
    global _SERVICE
    _SERVICE = IdeaGenerationService(runner=runner, command_template=command_template, workdir=workdir)


def get_proposals(limit: int = 10) -> list[ImprovementProposal]:
    """Return proposals."""
    if _SERVICE is None:
        raise RuntimeError("Auto-improve idea catalog is not configured.")
    return _SERVICE.generate(limit)
