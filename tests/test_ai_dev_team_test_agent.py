from ai_dev_team.test_agent import TestAgent


class _Proc:
    def __init__(self, returncode=0):
        self.returncode = returncode
        self.stdout = "ok"
        self.stderr = ""


def test_test_agent_uses_safe_default_pytest_command(monkeypatch, tmp_path):
    captured = {}

    def _fake_run(command, cwd, shell, text, capture_output):
        captured["command"] = command
        captured["cwd"] = cwd
        captured["shell"] = shell
        captured["text"] = text
        captured["capture_output"] = capture_output
        return _Proc(returncode=0)

    monkeypatch.setattr("ai_dev_team.test_agent.subprocess.run", _fake_run)

    result = TestAgent().run(tmp_path)

    assert "test_ai_dev_team_repo_analyzer.py" in captured["command"]
    assert captured["cwd"] == tmp_path
    assert captured["shell"] is True
    assert result.ok is True

