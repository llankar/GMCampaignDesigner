from __future__ import annotations

import shlex
import subprocess
import tempfile
import os
from pathlib import Path


class CommandExecutionError(RuntimeError):
    pass


class CommandRunner:
    def run_agent(self, command_template: str, prompt: str, workdir: Path) -> str:
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as handle:
            handle.write(prompt)
            prompt_path = Path(handle.name)

        try:
            prompt_file_value = self._quote_value(str(prompt_path))
            prompt_value = self._quote_value(prompt)

            command = (
                command_template.replace("{prompt_file}", prompt_file_value).replace("{prompt}", prompt_value)
            )
            result = self._run_shell(command=command, workdir=workdir)

            stderr = result.stderr or ""
            if result.returncode != 0 and "unexpected argument" in stderr and "--input-file" in command_template:
                fallback_command = self._build_prompt_fallback_template(command_template)
                fallback_command = fallback_command.replace("{prompt_file}", prompt_file_value).replace("{prompt}", prompt_value)
                result = self._run_shell(command=fallback_command, workdir=workdir)
                command = fallback_command

            output = (result.stdout or "") + ("\n" + result.stderr if result.stderr else "")
            if result.returncode != 0:
                raise CommandExecutionError(
                    f"Agent command failed with code {result.returncode}.\nCommand: {command}\n{output.strip()}"
                )
            return output.strip() or "Agent command completed without console output."
        finally:
            prompt_path.unlink(missing_ok=True)

    @staticmethod
    def _run_shell(command: str, workdir: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            command,
            shell=True,
            cwd=str(workdir),
            capture_output=True,
            text=True,
            check=False,
        )

    @staticmethod
    def _quote_value(value: str) -> str:
        if os.name == "nt":
            return subprocess.list2cmdline([value])
        return shlex.quote(value)

    @staticmethod
    def _build_prompt_fallback_template(command_template: str) -> str:
        fallback = command_template.replace("--input-file {prompt_file}", "{prompt}")
        fallback = fallback.replace("--input-file={prompt_file}", "{prompt}")
        if fallback == command_template:
            fallback = fallback.replace("{prompt_file}", "{prompt}")
        return fallback

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
