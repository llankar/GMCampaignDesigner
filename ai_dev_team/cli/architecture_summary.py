from __future__ import annotations

from pathlib import Path

try:
    from ..repo_analyzer import architecture_summary_text
except ImportError:
    from repo_analyzer import architecture_summary_text


def build_architecture_summary(workspace: str | Path = ".") -> str:
    """Return a concise architecture snapshot for the provided workspace."""
    return architecture_summary_text(workspace)
