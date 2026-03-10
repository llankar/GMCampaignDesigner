from __future__ import annotations

import shlex
import subprocess
import tempfile
from pathlib import Path


class CommandExecutionError(RuntimeError):
    pass


class CommandRunner:
    def run_agent(self, command_template: str, prompt: str, workdir: Path) -> str:
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as handle:
            handle.write(prompt)
            prompt_path = Path(handle.name)

        try:
            command = command_template.replace("{prompt_file}", shlex.quote(str(prompt_path)))
            result = subprocess.run(
                command,
                shell=True,
                cwd=str(workdir),
                capture_output=True,
                text=True,
                check=False,
            )
            output = (result.stdout or "") + ("\n" + result.stderr if result.stderr else "")
            if result.returncode != 0:
                raise CommandExecutionError(
                    f"Agent command failed with code {result.returncode}.\nCommand: {command}\n{output.strip()}"
                )
            return output.strip() or "Agent command completed without console output."
        finally:
            prompt_path.unlink(missing_ok=True)

    def run_validation(self, command: str, workdir: Path) -> str:
        result = subprocess.run(
            command,
            shell=True,
            cwd=str(workdir),
            capture_output=True,
            text=True,
            check=False,
        )
        output = (result.stdout or "") + ("\n" + result.stderr if result.stderr else "")
        if result.returncode != 0:
            raise CommandExecutionError(
                f"Validation command failed with code {result.returncode}.\nCommand: {command}\n{output.strip()}"
            )
        return output.strip() or "Validation completed without console output."
