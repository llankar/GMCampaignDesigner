from __future__ import annotations

import hashlib
import json
import sqlite3
import zipfile
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from modules.generic.campaign_sync.metadata_store import (
    CampaignSyncMetadataStore,
    InstallationStateStore,
)
from modules.generic.campaign_sync.models import CampaignSyncMetadata
from modules.generic.campaign_sync.updater import CampaignUpdateError, CampaignUpdater


def _metadata(
    campaign_id: str, revision: int, parent: int | None, digest: str = "0" * 64
):
    return CampaignSyncMetadata(
        campaign_id=campaign_id,
        revision=revision,
        parent_revision=parent,
        snapshot_sha256=digest,
        published_at="2026-07-26T00:00:00Z",
        publisher_installation_id="computer-a",
        bundle_version=1,
    )


def _campaign(
    path: Path, campaign_id: str, revision: int = 1, value: str = "old"
) -> Path:
    path.mkdir()
    database = path / "campaign.db"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE items (value TEXT)")
        connection.execute("INSERT INTO items VALUES (?)", (value,))
    (path / "assets").mkdir()
    (path / "assets" / "obsolete.txt").write_text("delete me", encoding="utf-8")
    CampaignSyncMetadataStore(path).write(
        _metadata(campaign_id, revision, revision - 1 or None)
    )
    return path


def _bundle(
    tmp_path: Path,
    campaign_id: str,
    *,
    revision=2,
    parent=1,
    version=1,
    mode="full_campaign",
    member_name=None,
) -> tuple[Path, object]:
    source = tmp_path / f"source-{uuid4().hex}"
    source.mkdir()
    database = source / "new.db"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE items (value TEXT)")
        connection.execute("INSERT INTO items VALUES ('new')")
    asset = source / "new.txt"
    asset.write_text("new asset", encoding="utf-8")
    manifest = {
        "version": version,
        "bundle_mode": mode,
        "database": {
            "file_name": "campaign.db",
            "relative_path": "database/campaign.db",
            "sha256": hashlib.sha256(database.read_bytes()).hexdigest(),
        },
        "assets": [
            {
                "bundle_path": "payload/new.txt",
                "original_path": "assets/new.txt",
                "sha256": hashlib.sha256(asset.read_bytes()).hexdigest(),
            }
        ],
        "sync": _metadata(campaign_id, revision, parent).to_dict(),
    }
    archive = tmp_path / f"bundle-{uuid4().hex}.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr(member_name or "manifest.json", json.dumps(manifest))
        bundle.write(database, "database/campaign.db")
        bundle.write(asset, "payload/new.txt")
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    release = SimpleNamespace(
        campaign_id=campaign_id,
        revision=revision,
        parent_revision=parent,
        snapshot_sha256=digest,
        snapshot_mode=mode,
    )
    return archive, release


class Client:
    def __init__(self, archive: Path, failure: Exception | None = None):
        self.archive, self.failure = archive, failure

    def download_bundle(self, release, destination, progress_callback=None):
        destination.write_bytes(
            self.archive.read_bytes()[:20]
            if self.failure
            else self.archive.read_bytes()
        )
        if self.failure:
            raise self.failure
        return destination


def _updater(tmp_path, archive, **kwargs):
    store = InstallationStateStore(tmp_path / "installation.json")

    def backup(path):
        Path(path).write_bytes(b"backup")

    return CampaignUpdater(
        Client(archive),
        installation_store=store,
        backup_creator=kwargs.pop("backup_creator", backup),
        **kwargs,
    )


def test_interrupted_download_does_not_replace_campaign(tmp_path):
    campaign_id, active = str(uuid4()), None
    active = _campaign(tmp_path / "campaign", campaign_id)
    archive, release = _bundle(tmp_path, campaign_id)
    updater = CampaignUpdater(
        Client(archive, IOError("interrupted")), backup_creator=lambda p: None
    )
    with pytest.raises(IOError, match="interrupted"):
        updater.install(active, release)
    assert (active / "assets" / "obsolete.txt").exists()


def test_checksum_mismatch_is_rejected(tmp_path):
    campaign_id = str(uuid4())
    active = _campaign(tmp_path / "campaign", campaign_id)
    archive, release = _bundle(tmp_path, campaign_id)
    release.snapshot_sha256 = "f" * 64
    with pytest.raises(CampaignUpdateError, match="archive SHA-256"):
        _updater(tmp_path, archive).install(active, release)


def test_invalid_zip_path_is_rejected(tmp_path):
    campaign_id = str(uuid4())
    active = _campaign(tmp_path / "campaign", campaign_id)
    archive, release = _bundle(tmp_path, campaign_id, member_name="../manifest.json")
    with pytest.raises(CampaignUpdateError, match="Invalid campaign ZIP"):
        _updater(tmp_path, archive).install(active, release)


@pytest.mark.parametrize(
    ("campaign_override", "version", "mode", "message"),
    [
        (True, 1, "full_campaign", "Campaign ID"),
        (False, 99, "full_campaign", "Unsupported bundle version"),
        (False, 1, "asset_bundle", "Asset-only"),
    ],
)
def test_invalid_bundle_identity_version_and_mode(
    tmp_path, campaign_override, version, mode, message
):
    campaign_id = str(uuid4())
    active = _campaign(tmp_path / "campaign", campaign_id)
    archive, release = _bundle(
        tmp_path,
        str(uuid4()) if campaign_override else campaign_id,
        version=version,
        mode=mode,
    )
    if campaign_override:
        release.campaign_id = campaign_id
    with pytest.raises(CampaignUpdateError, match=message):
        _updater(tmp_path, archive).install(active, release)


def test_backup_failure_prevents_quiesce_and_replacement(tmp_path):
    campaign_id = str(uuid4())
    active = _campaign(tmp_path / "campaign", campaign_id)
    archive, release = _bundle(tmp_path, campaign_id)
    quiesced = []

    def fail(_):
        raise OSError("disk full")

    with pytest.raises(CampaignUpdateError, match="backup"):
        _updater(
            tmp_path,
            archive,
            backup_creator=fail,
            quiesce=lambda: quiesced.append(True),
        ).install(active, release)
    assert not quiesced and (active / "assets" / "obsolete.txt").exists()


def test_first_rename_failure_leaves_active_campaign(tmp_path):
    campaign_id = str(uuid4())
    active = _campaign(tmp_path / "campaign", campaign_id)
    archive, release = _bundle(tmp_path, campaign_id)

    def fail(source, destination):
        raise OSError("rename denied")

    with pytest.raises(CampaignUpdateError, match="replacement failed"):
        _updater(tmp_path, archive, replace=fail).install(active, release)
    assert (active / "assets" / "obsolete.txt").exists()


def test_database_reopen_failure_restores_previous_campaign(tmp_path):
    campaign_id = str(uuid4())
    active = _campaign(tmp_path / "campaign", campaign_id)
    archive, release = _bundle(tmp_path, campaign_id)
    calls = []

    def reopen():
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("UI database rejected")

    with pytest.raises(CampaignUpdateError, match="previous campaign restored"):
        _updater(tmp_path, archive, reopen=reopen).install(active, release)
    assert len(calls) == 2
    assert (active / "assets" / "obsolete.txt").read_text() == "delete me"
    assert not list(tmp_path.glob(".campaign.rollback-*"))


def test_two_computer_full_snapshot_integration(tmp_path):
    campaign_id = str(uuid4())
    computer_a = _campaign(tmp_path / "computer-a", campaign_id)
    computer_b = _campaign(tmp_path / "computer-b", campaign_id)
    archive, release = _bundle(tmp_path, campaign_id)
    receipt = _updater(tmp_path, archive).install(computer_b, release)
    assert receipt.revision == 2 and receipt.backup_path.is_file()
    assert not (computer_b / "assets" / "obsolete.txt").exists()
    assert (computer_b / "assets" / "new.txt").read_text() == "new asset"
    with sqlite3.connect(computer_b / "campaign.db") as connection:
        assert connection.execute("SELECT value FROM items").fetchone()[0] == "new"
    assert CampaignSyncMetadataStore(computer_b).read().revision == 2
    assert CampaignSyncMetadataStore(computer_a).read().revision == 1
