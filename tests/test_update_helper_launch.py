"""Regression tests for update helper launch."""

import subprocess
import sys
import types
from pathlib import Path

import pytest
from packaging.version import Version

if "requests" not in sys.modules:
    requests_stub = types.ModuleType("requests")

    class _Session:
        def __init__(self, *args, **kwargs):
            """Initialize the _Session instance."""
            self.headers = {}

        def get(self, *args, **kwargs):
            """Return the operation."""
            return None

        def close(self):
            """Close the operation."""
            pass

    requests_stub.Session = _Session
    requests_stub.get = lambda *args, **kwargs: None
    sys.modules["requests"] = requests_stub

from modules.helpers import update_helper


class _DummyProcess:
    pid = 123


def test_launch_installer_uses_helper_script_when_not_frozen(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Verify that launch installer uses helper script when not frozen."""
    helper = tmp_path / "apply_update.py"
    helper.write_text("print('ok')", encoding="utf-8")

    monkeypatch.setattr(update_helper, "_INSTALL_HELPER", helper)
    monkeypatch.setattr(sys, "frozen", False, raising=False)

    captured: dict[str, list[str]] = {}

    def _fake_popen(args, close_fds=False):
        """Internal helper for fake popen."""
        captured["args"] = list(args)
        return _DummyProcess()

    monkeypatch.setattr(subprocess, "Popen", _fake_popen)

    payload = tmp_path / "payload"
    payload.mkdir()

    update_helper.launch_installer(payload, install_root=tmp_path)

    assert captured["args"][0] == sys.executable
    assert captured["args"][1] == str(helper)
    assert "--apply-update" not in captured["args"]


def test_launch_installer_copies_helper_when_frozen(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Verify that launch installer copies helper when frozen."""
    helper_dir = tmp_path / "frozen"
    helper_dir.mkdir()
    helper = helper_dir / update_helper._FROZEN_INSTALL_HELPER_NAME
    helper.write_text("print('ok')", encoding="utf-8")

    executable = helper_dir / "GMCampaignDesigner.exe"
    executable.write_text("stub", encoding="utf-8")

    monkeypatch.setattr(sys, "executable", str(executable), raising=False)
    monkeypatch.setattr(sys, "frozen", True, raising=False)

    temp_dirs: list[Path] = []

    def _fake_mkdtemp(prefix="", dir=None):  # noqa: ANN001
        """Internal helper for fake mkdtemp."""
        path = tmp_path / f"temp-{len(temp_dirs)}"
        path.mkdir()
        temp_dirs.append(path)
        return str(path)

    monkeypatch.setattr(update_helper.tempfile, "mkdtemp", _fake_mkdtemp)

    captured: dict[str, list[str]] = {}

    def _fake_popen(args, close_fds=False):
        """Internal helper for fake popen."""
        captured["args"] = list(args)
        return _DummyProcess()

    monkeypatch.setattr(subprocess, "Popen", _fake_popen)

    payload = tmp_path / "payload"
    payload.mkdir()

    update_helper.launch_installer(payload, install_root=tmp_path)

    copied_helper = Path(captured["args"][0])
    assert copied_helper.parent in temp_dirs
    assert copied_helper.parent != helper.parent
    assert copied_helper.name == helper.name
    assert copied_helper.read_text(encoding="utf-8") == helper.read_text(encoding="utf-8")
    assert str(helper) not in captured["args"]

    cleanup_indices = [i for i, value in enumerate(captured["args"]) if value == "--cleanup-root"]
    assert cleanup_indices, "expected cleanup root to be provided"
    for index in cleanup_indices:
        assert Path(captured["args"][index + 1]) in temp_dirs


class _FakeResponse:
    def __init__(self, payload):
        """Initialize the fake response."""
        self._payload = payload

    def raise_for_status(self):
        """Simulate a successful response status."""
        return None

    def json(self):
        """Return the fake JSON payload."""
        return self._payload


class _FakeSession:
    def __init__(self, payload):
        """Initialize the fake session."""
        self.headers = {}
        self._payload = payload

    def get(self, *_args, **_kwargs):
        """Return a fake releases response."""
        return _FakeResponse(self._payload)


def test_check_for_update_skips_gallery_bundle_release_tags(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify gallery bundle releases do not crash the application updater."""
    monkeypatch.setattr(update_helper, "read_installed_version", lambda: Version("1.0.0"))
    session = _FakeSession(
        [
            {
                "draft": False,
                "prerelease": False,
                "tag_name": "bundle-fallout-20260509-091119",
                "assets": [
                    {
                        "name": "fallout-bundle.zip",
                        "browser_download_url": "https://example.invalid/fallout-bundle.zip",
                        "size": 123,
                    }
                ],
            },
            {
                "draft": False,
                "prerelease": False,
                "tag_name": "v1.0.1",
                "assets": [
                    {
                        "name": "GMCampaignDesigner.zip",
                        "browser_download_url": "https://example.invalid/GMCampaignDesigner.zip",
                        "size": 456,
                    }
                ],
            },
        ]
    )

    _current, candidate = update_helper.check_for_update(session=session)

    assert candidate is not None
    assert candidate.tag == "v1.0.1"
    assert candidate.version == Version("1.0.1")


def test_normalize_tag_accepts_prefixed_and_plain_version_tags() -> None:
    """Verify application release tags are accepted with or without a v prefix."""
    assert update_helper._normalize_tag("v1.2.3") == Version("1.2.3")
    assert update_helper._normalize_tag("1.2.3") == Version("1.2.3")


def test_normalize_tag_rejects_non_application_bundle_tags() -> None:
    """Verify non-application release tags are rejected with a controlled error."""
    with pytest.raises(RuntimeError, match="valid application version"):
        update_helper._normalize_tag("bundle-fallout-20260509-091119")
