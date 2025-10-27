import subprocess
import sys
import types
from pathlib import Path

import pytest

if "requests" not in sys.modules:
    requests_stub = types.ModuleType("requests")

    class _Session:
        def __init__(self, *args, **kwargs):
            self.headers = {}

        def get(self, *args, **kwargs):
            return None

        def close(self):
            pass

    requests_stub.Session = _Session
    requests_stub.get = lambda *args, **kwargs: None
    sys.modules["requests"] = requests_stub

from modules.helpers import update_helper


class _DummyProcess:
    pid = 123


def test_launch_installer_uses_helper_script_when_not_frozen(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    helper = tmp_path / "apply_update.py"
    helper.write_text("print('ok')", encoding="utf-8")

    monkeypatch.setattr(update_helper, "_INSTALL_HELPER", helper)
    monkeypatch.setattr(sys, "frozen", False, raising=False)

    captured: dict[str, list[str]] = {}

    def _fake_popen(args, close_fds=False):
        captured["args"] = list(args)
        return _DummyProcess()

    monkeypatch.setattr(subprocess, "Popen", _fake_popen)

    payload = tmp_path / "payload"
    payload.mkdir()

    update_helper.launch_installer(payload, install_root=tmp_path)

    assert captured["args"][0] == sys.executable
    assert captured["args"][1] == str(helper)
    assert "--apply-update" not in captured["args"]


def test_launch_installer_uses_flag_when_frozen(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    helper = tmp_path / "apply_update.py"
    helper.write_text("print('ok')", encoding="utf-8")

    monkeypatch.setattr(update_helper, "_INSTALL_HELPER", helper)
    monkeypatch.setattr(sys, "frozen", True, raising=False)

    captured: dict[str, list[str]] = {}

    def _fake_popen(args, close_fds=False):
        captured["args"] = list(args)
        return _DummyProcess()

    monkeypatch.setattr(subprocess, "Popen", _fake_popen)

    payload = tmp_path / "payload"
    payload.mkdir()

    update_helper.launch_installer(payload, install_root=tmp_path)

    assert captured["args"][0] == sys.executable
    assert captured["args"][1] == "--apply-update"
    assert str(helper) not in captured["args"]
