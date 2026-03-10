from pathlib import Path

from modules.auto_improve.command_runner import CommandExecutionError, CommandRunner


def test_run_agent_fallbacks_when_input_file_flag_is_unsupported(monkeypatch, tmp_path):
    runner = CommandRunner()
    calls: list[str] = []

    def fake_run_shell(command: str, workdir: Path):
        calls.append(command)

        class Result:
            def __init__(self, returncode: int, stdout: str = "", stderr: str = ""):
                self.returncode = returncode
                self.stdout = stdout
                self.stderr = stderr

        if len(calls) == 1:
            return Result(2, stderr="error: unexpected argument '--input-file' found")
        return Result(0, stdout='[{"slug":"ok","title":"Ok","summary":"Ok","scope":"Ok","prompt":"Ok"}]')

    monkeypatch.setattr(CommandRunner, "_run_shell", staticmethod(fake_run_shell))

    output = runner.run_agent(
        command_template="codex exec --input-file {prompt_file}",
        prompt="Generate ideas",
        workdir=tmp_path,
    )

    assert len(calls) == 2
    assert "--input-file" in calls[0]
    assert "--input-file" not in calls[1]
    assert "Generate ideas" in calls[1]
    assert output.startswith("[")


def test_run_agent_raises_error_for_other_failures(monkeypatch, tmp_path):
    runner = CommandRunner()

    def fake_run_shell(command: str, workdir: Path):
        class Result:
            returncode = 1
            stdout = ""
            stderr = "other failure"

        return Result()

    monkeypatch.setattr(CommandRunner, "_run_shell", staticmethod(fake_run_shell))

    try:
        runner.run_agent(
            command_template="codex exec --input-file {prompt_file}",
            prompt="Generate ideas",
            workdir=tmp_path,
        )
    except CommandExecutionError as exc:
        assert "other failure" in str(exc)
    else:
        raise AssertionError("Expected CommandExecutionError")
