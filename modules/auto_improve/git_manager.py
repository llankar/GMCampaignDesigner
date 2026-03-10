from __future__ import annotations

import subprocess
from pathlib import Path


class GitManager:
    def __init__(self, workdir: Path):
        self.workdir = workdir

    def _run(self, args: list[str]) -> str:
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

    def create_branch(self, branch_name: str) -> None:
        self._run(["checkout", "-b", branch_name])

    def commit_all(self, message: str) -> None:
        self._run(["add", "-A"])
        status = self._run(["status", "--porcelain"])
        if not status:
            return
        self._run(["commit", "-m", message])
