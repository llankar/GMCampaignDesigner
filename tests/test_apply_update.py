from pathlib import Path

import pytest

import scripts.apply_update as apply_update


def test_copy_release_tree_preserves_campaigns_casefold(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        apply_update,
        "_normalize_parts",
        lambda parts: tuple(part.casefold() for part in parts),
        raising=False,
    )

    source = tmp_path / "payload"
    target = tmp_path / "install"
    source.mkdir()
    target.mkdir()

    preserved_dir = target / "Campaigns"
    preserved_dir.mkdir()
    preserved_file = preserved_dir / "existing.txt"
    preserved_file.write_text("keep me")

    campaigns_payload = source / "campaigns"
    campaigns_payload.mkdir()
    (campaigns_payload / "new.txt").write_text("replace?")

    other_dir = source / "other"
    other_dir.mkdir()
    (other_dir / "file.txt").write_text("copy me")

    preserved = {apply_update._normalize_preserve_path("Campaigns")}
    apply_update._copy_release_tree(source, target, preserved)

    assert (target / "other" / "file.txt").read_text() == "copy me"
    assert preserved_file.read_text() == "keep me"
    assert not (target / "Campaigns" / "new.txt").exists()


def test_wait_for_pid_permission_error_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(apply_update.os, "name", "nt", raising=False)
    monkeypatch.setattr(apply_update, "_is_pid_alive_windows", lambda pid: None)

    kill_calls = {"count": 0}

    def fake_kill(pid: int, signal: int) -> None:
        kill_calls["count"] += 1
        exc = PermissionError()
        setattr(exc, "winerror", 5)
        raise exc

    monkeypatch.setattr(apply_update.os, "kill", fake_kill, raising=False)

    class FakeClock:
        def __init__(self) -> None:
            self.current = 0.0
            self.sleeps: list[float] = []

        def time(self) -> float:
            return self.current

        def sleep(self, amount: float) -> None:
            self.sleeps.append(amount)
            self.current += amount

    clock = FakeClock()
    monkeypatch.setattr(apply_update.time, "time", clock.time)
    monkeypatch.setattr(apply_update.time, "sleep", clock.sleep)

    with pytest.raises(SystemExit):
        apply_update._wait_for_pid(1234, timeout=1)

    assert kill_calls["count"] > 1
    assert clock.sleeps
