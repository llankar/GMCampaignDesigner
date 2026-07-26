import sqlite3
import zipfile

import pytest

from modules.generic.campaign_sync.change_detector import (
    CampaignChangeDetector,
    CampaignChangeState,
    calculate_campaign_fingerprint,
    create_campaign_backup_archive,
)
from modules.generic.campaign_sync.metadata_store import InstallationStateStore


@pytest.fixture
def campaign(tmp_path):
    root = tmp_path / "campaign"
    root.mkdir()
    connection = sqlite3.connect(root / "campaign.db")
    connection.execute("CREATE TABLE notes (id INTEGER PRIMARY KEY, body TEXT)")
    connection.execute("INSERT INTO notes(body) VALUES ('original')")
    connection.commit()
    connection.close()
    files = {
        "image": root / "assets/image_library/scene.png",
        "attachment": root / "assets/attachments/handout.pdf",
        "gm_table": root / "gm_table_layouts.json",
        "extra": root / "static/data/random_tables.json",
    }
    for path, value in zip(files.values(), (b"image", b"attachment", b"[]", b"{}")):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(value)
    return root, files


def _detector(tmp_path, root):
    detector = CampaignChangeDetector(
        InstallationStateStore(tmp_path / "installation.json")
    )
    detector.persist_baseline(root)
    assert detector.detect(root).state is CampaignChangeState.CLEAN
    return detector


def test_database_mutation_marks_campaign_dirty(tmp_path, campaign):
    root, _ = campaign
    detector = _detector(tmp_path, root)
    connection = sqlite3.connect(root / "campaign.db")
    connection.execute("INSERT INTO notes(body) VALUES ('changed')")
    connection.commit()
    connection.close()
    assert detector.detect(root).state is CampaignChangeState.LOCALLY_MODIFIED


@pytest.mark.parametrize("file_key", ["image", "attachment", "gm_table", "extra"])
def test_synchronized_file_mutation_marks_campaign_dirty(tmp_path, campaign, file_key):
    root, files = campaign
    detector = _detector(tmp_path, root)
    files[file_key].write_bytes(files[file_key].read_bytes() + b"changed")
    assert detector.detect(root).state is CampaignChangeState.LOCALLY_MODIFIED


def test_transient_and_sync_metadata_do_not_change_fingerprint(campaign):
    root, _ = campaign
    baseline = calculate_campaign_fingerprint(root)
    transient = root / "assets/image_library/upload.tmp"
    transient.write_bytes(b"in progress")
    sync = root / ".gmcd/sync.json"
    sync.parent.mkdir()
    sync.write_text('{"revision": 999}', encoding="utf-8")
    (root / "campaign.db-wal").write_bytes(b"transient")
    assert calculate_campaign_fingerprint(root) == baseline


def test_repeated_sqlite_snapshots_are_deterministic(campaign):
    root, _ = campaign
    assert calculate_campaign_fingerprint(root) == calculate_campaign_fingerprint(root)


def test_missing_baseline_and_fingerprint_failure_are_unknown(tmp_path, campaign):
    root, _ = campaign
    store = InstallationStateStore(tmp_path / "installation.json")
    detector = CampaignChangeDetector(store)
    assert detector.detect(root).state is CampaignChangeState.UNKNOWN
    detector.persist_baseline(root)
    (root / "campaign.db").unlink()
    result = detector.detect(root)
    assert result.state is CampaignChangeState.UNKNOWN
    assert result.error


def test_backup_archive_contains_readable_sqlite_snapshot(tmp_path, campaign):
    root, _ = campaign
    archive = create_campaign_backup_archive(root, tmp_path / "backup.zip")
    restored = tmp_path / "restored"
    with zipfile.ZipFile(archive) as bundle:
        bundle.extractall(restored)
    connection = sqlite3.connect(restored / "campaign.db")
    try:
        assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)
        assert connection.execute("SELECT body FROM notes").fetchall() == [("original",)]
    finally:
        connection.close()
