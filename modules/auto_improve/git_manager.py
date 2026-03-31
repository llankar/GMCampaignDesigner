"""Management helpers for auto improve git."""

from __future__ import annotations

import subprocess
from pathlib import Path


class GitManager:
    def __init__(self, workdir: Path):
        """Initialize the GitManager instance."""
        self.workdir = workdir

    def _run(self, args: list[str]) -> str:
        """Run the operation."""
        result = subprocess.run(
            ["git", *args],
            cwd=str(self.workdir),
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            err = (result.stderr or result.stdout or "").strip()
            raise RuntimeError(f"git {' '.join(args)} failed: {err}")
        return (result.stdout or "").strip()


    def commit_all(self, message: str) -> None:
        """Handle commit all."""
        self._run(["add", "-A"])
        status = self._run(["status", "--porcelain"])
        if not status:
            return
        self._run(["commit", "-m", message])
