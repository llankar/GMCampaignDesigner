"""Test agent running pytest and returning structured results."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

try:
    from .execution import DEFAULT_SAFE_TEST_COMMAND
except ImportError:
    from execution import DEFAULT_SAFE_TEST_COMMAND


@dataclass
class TestResult:
    ok: bool
    command: str
    return_code: int
    output: str


class TestAgent:
    """Run pytest to ensure feature work does not break the repository."""

    def run(self, workspace: str | Path = ".", command: str = DEFAULT_SAFE_TEST_COMMAND) -> TestResult:
        proc = subprocess.run(
            command,
            cwd=Path(workspace),
            shell=True,
            text=True,
            capture_output=True,
        )
        output = (proc.stdout or "") + ("\n" + proc.stderr if proc.stderr else "")
        return TestResult(
            ok=proc.returncode == 0,
            command=command,
            return_code=proc.returncode,
            output=output.strip(),
        )
