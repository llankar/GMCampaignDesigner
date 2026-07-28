from __future__ import annotations

import json
import os
import shutil
import sqlite3
import zipfile
from pathlib import Path

import pytest

from modules.generic.campaign_sync.change_detector import calculate_campaign_fingerprint
from modules.generic.campaign_sync.delta_applier import apply_delta, clone_campaign
from modules.generic.campaign_sync.delta_builder import (
    build_inventory,
    compare_inventories,
    write_delta_bundle,
)
from modules.generic.campaign_sync.delta_manifest import DeltaManifest, InventoryEntry
from modules.generic.campaign_sync.hashing import sha256_file
from modules.generic.campaign_sync.metadata_store import CampaignSyncMetadataStore
from modules.generic.campaign_sync.models import CampaignSyncMetadata
from modules.generic.campaign_sync.updater import (
    CampaignUpdateError,
    CampaignUpdateReceipt,
    CampaignUpdater,
)


def _database(path: Path, value: str) -> Path:
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE content (value TEXT)")
        connection.execute("INSERT INTO content VALUES (?)", (value,))
    return path


def _campaign(root: Path, value: str = "one") -> Path:
    root.mkdir()
    database = _database(root / "campaign.db", value)
    (root / "assets").mkdir()
    (root / "assets" / "changed.bin").write_bytes(b"old")
    (root / "assets" / "deleted.bin").write_bytes(b"delete")
    (root / "world_maps").mkdir()
    (root / "world_maps" / "renamed-old.png").write_bytes(b"map")
    return database


def test_inventory_diff_tracks_content_not_timestamps_and_models_rename(tmp_path):
    root = tmp_path / "campaign"
    database = _campaign(root)
    before = build_inventory(root, database, database_snapshot_path=database)
    changed = root / "assets" / "changed.bin"
    old_stat = changed.stat()
    changed.write_bytes(b"new")
    os.utime(changed, (old_stat.st_atime, old_stat.st_mtime))
    (root / "assets" / "new.bin").write_bytes(b"new file")
    (root / "assets" / "deleted.bin").unlink()
    (root / "world_maps" / "renamed-old.png").rename(
        root / "world_maps" / "renamed-new.png"
    )

    after = build_inventory(root, database, database_snapshot_path=database)
    files, tombstones = compare_inventories(before, after)

    assert {entry.path for entry in files} == {
        "assets/changed.bin",
        "assets/new.bin",
        "world_maps/renamed-new.png",
    }
    assert set(tombstones) == {
        "assets/deleted.bin",
        "world_maps/renamed-old.png",
    }
    assert all(len(entry.sha256) == 64 and entry.size >= 0 for entry in after)
    assert {entry.file_type for entry in after} >= {"database", "asset"}


def test_delta_reconstruction_matches_inventory_and_canonical_fingerprint(tmp_path):
    active = tmp_path / "active"
    active_db = _campaign(active)
    baseline = build_inventory(active, active_db, database_snapshot_path=active_db)
    base_fingerprint = calculate_campaign_fingerprint(
        active, database_path=active_db, database_snapshot_path=active_db
    )

    publisher = tmp_path / "publisher"
    shutil.copytree(active, publisher)
    (publisher / "assets" / "changed.bin").write_bytes(b"replacement")
    (publisher / "assets" / "deleted.bin").unlink()
    (publisher / "assets" / "new.bin").write_bytes(b"new")
    publisher_db = publisher / "campaign.db"
    with sqlite3.connect(publisher_db) as connection:
        connection.execute("INSERT INTO content VALUES ('two')")
    current = build_inventory(publisher, publisher_db, database_snapshot_path=publisher_db)
    fingerprint = calculate_campaign_fingerprint(
        publisher, database_path=publisher_db, database_snapshot_path=publisher_db
    )
    archive = tmp_path / "delta.zip"
    manifest = write_delta_bundle(
        archive,
        publisher,
        publisher_db,
        "campaign.db",
        {"bundle_version": 1, "snapshot_sha256": fingerprint},
        1,
        base_fingerprint,
        baseline,
        current,
    )
    extracted = tmp_path / "extracted"
    with zipfile.ZipFile(archive) as bundle:
        bundle.extractall(extracted)
    staging = tmp_path / "staging"
    clone_campaign(active, staging)
    delta = DeltaManifest.from_dict(manifest["delta"])

    target_db = apply_delta(extracted, staging, delta, manifest["database"])

    assert build_inventory(staging, target_db, database_snapshot_path=target_db) == current
    assert calculate_campaign_fingerprint(
        staging, database_path=target_db, database_snapshot_path=target_db
    ) == fingerprint
    assert not (staging / "assets" / "deleted.bin").exists()
    assert (staging / "assets" / "changed.bin").read_bytes() == b"replacement"
    # Hard-link staging must not mutate the currently installed campaign.
    assert (active / "assets" / "changed.bin").read_bytes() == b"old"


def test_delta_rejects_corrupted_payload_and_traversal(tmp_path):
    payload = tmp_path / "payload.bin"
    payload.write_bytes(b"expected")
    entry = InventoryEntry("assets/file.bin", sha256_file(payload), 8, "asset")
    delta = DeltaManifest(1, "a" * 64, (entry,), (), (entry,))
    extracted = tmp_path / "extracted"
    (extracted / "payload" / "assets").mkdir(parents=True)
    (extracted / "payload" / "assets" / "file.bin").write_bytes(b"corrupt!")
    database = _database(extracted / "db.sqlite", "new")
    staging = tmp_path / "staging"
    staging.mkdir()

    with pytest.raises(ValueError, match="corrupted delta payload"):
        apply_delta(
            extracted,
            staging,
            delta,
            {"relative_path": "db.sqlite", "sha256": sha256_file(database), "file_name": "campaign.db"},
        )
    with pytest.raises(ValueError, match="invalid synchronized-content path"):
        InventoryEntry("../escape", "a" * 64, 1, "asset")
    with pytest.raises(ValueError, match="invalid synchronized-content path"):
        DeltaManifest(1, "a" * 64, (), ("assets/../../escape",), ())


def test_delta_manifest_static_contract_is_versioned_and_requires_exact_base():
    entry = InventoryEntry("assets/a", "b" * 64, 3, "asset")
    manifest = DeltaManifest(7, "c" * 64, (entry,), (), (entry,))

    serialized = json.loads(json.dumps(manifest.to_dict()))

    assert serialized["version"] == 1
    assert serialized["base_revision"] == 7
    assert serialized["base_content_fingerprint"] == "c" * 64
    assert serialized["inventory"][0] == {
        "path": "assets/a",
        "sha256": "b" * 64,
        "size": 3,
        "file_type": "asset",
    }
    with pytest.raises(ValueError, match="unsupported delta manifest"):
        DeltaManifest.from_dict({**serialized, "version": 2})


def test_install_chain_rejects_missing_delta_and_can_fall_back_to_full_checkpoint(tmp_path, monkeypatch):
    root = tmp_path / "campaign"
    root.mkdir()
    campaign_id = "12345678-1234-5678-1234-567812345678"

    def write_revision(revision: int) -> None:
        CampaignSyncMetadataStore(root).write(
            CampaignSyncMetadata(
                campaign_id,
                revision,
                revision - 1 or None,
                "a" * 64,
                "2026-07-28T00:00:00Z",
                "publisher",
                1,
            )
        )

    write_revision(1)
    updater = CampaignUpdater(object(), backup_creator=lambda _: None)
    installed: list[int] = []

    def install(_root, release, **_kwargs):
        installed.append(release.revision)
        write_revision(release.revision)
        return CampaignUpdateReceipt(root, release.revision, tmp_path / "backup.zip", "b" * 64)

    monkeypatch.setattr(updater, "install", install)
    delta3 = type("Release", (), {"revision": 3, "snapshot_mode": "campaign_delta", "base_revision": 2})()
    with pytest.raises(CampaignUpdateError, match="incomplete"):
        updater.install_chain(root, [delta3])

    checkpoint = type("Release", (), {"revision": 5, "snapshot_mode": "full_campaign", "base_revision": None})()
    delta6 = type("Release", (), {"revision": 6, "snapshot_mode": "campaign_delta", "base_revision": 5})()
    receipts = updater.install_chain(root, [delta6, checkpoint])

    assert [receipt.revision for receipt in receipts] == [5, 6]
    assert installed == [5, 6]
