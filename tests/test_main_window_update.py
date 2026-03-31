"""Regression tests for main window update."""

from pathlib import Path
import sys

import pytest
from packaging.version import Version

import main_window
from modules.helpers import update_helper


class _DummyApp:
    def __init__(self):
        """Initialize the _DummyApp instance."""
        self.worker_result = None

    def _run_progress_task(self, title, worker, success_message, detail_builder=None):
        """Run progress task."""
        # Execute the worker immediately to capture its arguments
        self.worker_result = worker(lambda *_args, **_kwargs: None)
        if detail_builder:
            detail_builder(self.worker_result)


def test_begin_update_download_uses_project_root(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Verify that begin update download uses project root."""
    candidate = update_helper.UpdateCandidate(
        version=Version("2.0.0"),
        tag="v2.0.0",
        asset_url="https://example.invalid/asset.zip",
        asset_name="asset.zip",
        asset_size=123,
        release_notes="",
        channel="stable",
    )

    stage_root = tmp_path / "stage"
    payload_root = tmp_path / "payload"
    stage_root.mkdir()
    payload_root.mkdir()

    monkeypatch.setattr(sys, "frozen", False, raising=False)

    monkeypatch.setattr(
        update_helper,
        "prepare_staging_area",
        lambda *_args, **_kwargs: (stage_root, payload_root),
    )

    captured_install_root: dict[str, Path] = {}

    class _Process:
        pid = 42

    def _fake_launch_installer(
        payload_root_arg,
        *,
        install_root,
        restart_target,
        wait_for_pid,
        preserve,
        cleanup_root,
    ):
        """Internal helper for fake launch installer."""
        captured_install_root["value"] = Path(install_root)
        return _Process()

    monkeypatch.setattr(update_helper, "launch_installer", _fake_launch_installer)

    app = _DummyApp()
    bound_method = main_window.MainWindow._begin_update_download.__get__(app, _DummyApp)
    bound_method(candidate)

    assert captured_install_root["value"] == Path(main_window.__file__).resolve().parent
