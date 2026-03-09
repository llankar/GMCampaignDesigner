from __future__ import annotations

import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass
class PRMetadata:
    branch: str
    commit_message: str


class PRAgent:
    def create_branch_and_commit(
        self,
        workspace: str | Path,
        message: str,
        branch_prefix: str = "feature-lab",
        push: bool = False,
    ) -> PRMetadata:
        cwd = Path(workspace)
        branch = f"{branch_prefix}/{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}"
        self._run(f"git checkout -b {branch}", cwd)
        self._run("git add -A", cwd)
        self._run(f"git commit -m {self._quote(message)}", cwd)
        if push:
            self._run(f"git push -u origin {branch}", cwd)
        return PRMetadata(branch, message)

    @staticmethod
    def _run(cmd: str, cwd: Path) -> None:
        proc = subprocess.run(cmd, cwd=cwd, shell=True, text=True, capture_output=True)
        if proc.returncode != 0:
            raise RuntimeError(f"Command failed: {cmd}\n{proc.stdout}\n{proc.stderr}")

    @staticmethod
    def _quote(text: str) -> str:
        return '"' + text.replace('"', "'") + '"'
