from pathlib import Path
from types import SimpleNamespace
import sqlite3
import zipfile
import json
import io

import pytest

from modules.generic.campaign_sync.change_detector import (
    CampaignChangeDetector,
    CampaignChangeState,
)
from modules.generic.campaign_sync.metadata_store import (
    CampaignSyncMetadataStore,
    InstallationStateStore,
)
from modules.generic.campaign_sync.hashing import sha256_file
from modules.generic.campaign_sync.publisher import (
    CampaignPublisher,
    PublishOutcome,
    StaleParentError,
)
from modules.generic.cross_campaign_asset_service import install_full_campaign_bundle


class MockGallery:
    def __init__(self):
        self.releases = []
        self.failures = 0
        self.duplicate_on_publish = False

    def highest_revision(self, campaign_id):
        if self.failures:
            self.failures -= 1
            raise OSError("temporary API failure")
        matches = [item for item in self.releases if item.campaign_id == campaign_id]
        return max(matches, key=lambda item: item.revision, default=None)

    def list_bundles(self):
        return list(self.releases)

    def publish_bundle(self, archive, manifest, **_kwargs):
        sync = manifest["sync"]
        archive_bytes = Path(archive).read_bytes()
        release = SimpleNamespace(
            **sync,
            archive=Path(archive),
            archive_sha256=sha256_file(Path(archive)),
            archive_bytes=archive_bytes,
        )
        self.releases.append(release)
        if self.duplicate_on_publish:
            self.releases.append(SimpleNamespace(**sync))
        return release


@pytest.fixture
def campaign(tmp_path):
    root = tmp_path / "Campaign"
    root.mkdir()
    database = root / "campaign.db"
    connection = sqlite3.connect(database)
    connection.execute("CREATE TABLE notes (value TEXT)")
    connection.execute("INSERT INTO notes VALUES ('one')")
    connection.commit()
    connection.close()
    asset = root / "assets" / "image_library" / "scene.png"
    asset.parent.mkdir(parents=True)
    asset.write_bytes(b"original image")
    return root, database


def _publisher(tmp_path, gallery, **kwargs):
    store = InstallationStateStore(tmp_path / "installation.json")
    return CampaignPublisher(gallery, installation_store=store, retry_delay=0, **kwargs)


def test_successful_sequential_publication(campaign, tmp_path):
    root, database = campaign
    gallery = MockGallery()
    publisher = _publisher(tmp_path, gallery)
    identity = publisher.enable(root, database_path=database)

    first = publisher.publish(root, database_path=database)
    connection = sqlite3.connect(database)
    connection.execute("INSERT INTO notes VALUES ('two')")
    connection.commit()
    connection.close()
    second = publisher.publish(root, database_path=database)

    assert first.outcome is PublishOutcome.PUBLISHED and first.revision == 1
    assert second.outcome is PublishOutcome.PUBLISHED and second.revision == 2
    assert second.campaign_id == identity.campaign_id
    with zipfile.ZipFile(io.BytesIO(second.release.archive_bytes)) as archive:
        assert json.loads(archive.read("manifest.json"))["sync"]["snapshot_mode"] == "campaign_delta"


def test_scheduled_checkpoint_is_full(campaign, tmp_path):
    root, database = campaign
    gallery = MockGallery()
    publisher = _publisher(tmp_path, gallery, checkpoint_interval=2)
    publisher.enable(root, database_path=database)
    publisher.publish(root, database_path=database)

    result = publisher.publish(root, database_path=database)

    with zipfile.ZipFile(io.BytesIO(result.release.archive_bytes)) as archive:
        manifest = json.loads(archive.read("manifest.json"))
    assert manifest["bundle_mode"] == "full_campaign"
    assert manifest["sync"]["snapshot_mode"] == "full_campaign"


def test_forced_checkpoint_at_incremental_revision_is_standalone(campaign, tmp_path):
    root, database = campaign
    (root / "gm_layouts.json").write_text('{"layout": "standalone"}', encoding="utf-8")
    gallery = MockGallery()
    publisher = _publisher(tmp_path, gallery, checkpoint_interval=10)
    publisher.enable(root, database_path=database)
    publisher.publish(root, database_path=database)

    result = publisher.publish(
        root, database_path=database, force_full_checkpoint=True
    )

    archive_path = tmp_path / "forced.zip"
    archive_path.write_bytes(result.release.archive_bytes)
    with zipfile.ZipFile(archive_path) as archive:
        manifest = json.loads(archive.read("manifest.json"))
        names = set(archive.namelist())
    assert manifest["bundle_mode"] == "full_campaign"
    assert manifest["sync"]["snapshot_mode"] == "full_campaign"
    assert manifest["database"]["relative_path"] in names
    extra = next(item for item in manifest["extra_files"] if item["relative_path"] == "gm_layouts.json")
    assert extra["bundle_path"] in names

    installed = install_full_campaign_bundle(archive_path, tmp_path / "installed")
    assert installed.db_path.is_file()
    assert (installed.root / "gm_layouts.json").read_text(encoding="utf-8") == '{"layout": "standalone"}'


def test_release_digest_authenticates_archive_and_bundle_retains_uuid(campaign, tmp_path):
    root, database = campaign
    gallery = MockGallery()
    publisher = _publisher(tmp_path, gallery)
    identity = publisher.enable(root, database_path=database)

    result = publisher.publish(root, database_path=database)

    assert result.snapshot_sha256 == result.release.archive_sha256
    assert CampaignSyncMetadataStore(root).read().snapshot_sha256 == result.release.archive_sha256
    with zipfile.ZipFile(io.BytesIO(result.release.archive_bytes)) as archive:
        manifest = json.loads(archive.read("manifest.json"))
    assert manifest["sync"]["campaign_id"] == identity.campaign_id


@pytest.mark.parametrize("changed_content", ["database", "asset"])
def test_publication_baseline_tracks_campaign_content(campaign, tmp_path, changed_content):
    root, database = campaign
    gallery = MockGallery()
    publisher = _publisher(tmp_path, gallery)
    publisher.enable(root, database_path=database)

    publisher.publish(root, database_path=database)

    detector = CampaignChangeDetector(publisher.installation_store)
    assert detector.detect(root, database_path=database).state is CampaignChangeState.CLEAN

    if changed_content == "database":
        connection = sqlite3.connect(database)
        connection.execute("INSERT INTO notes VALUES ('locally changed')")
        connection.commit()
        connection.close()
    else:
        (root / "assets" / "image_library" / "scene.png").write_bytes(b"locally changed image")

    assert (
        detector.detect(root, database_path=database).state
        is CampaignChangeState.LOCALLY_MODIFIED
    )


def test_stale_parent_is_rejected_before_release(campaign, tmp_path):
    root, database = campaign
    gallery = MockGallery()
    publisher = _publisher(tmp_path, gallery)
    identity = publisher.enable(root, database_path=database)
    gallery.releases.append(SimpleNamespace(campaign_id=identity.campaign_id, revision=2))

    with pytest.raises(StaleParentError, match="Download and reconcile"):
        publisher.publish(root, database_path=database)
    assert len(gallery.releases) == 1


def test_duplicate_revision_is_reported_without_advancing_local_state(campaign, tmp_path):
    root, database = campaign
    gallery = MockGallery()
    publisher = _publisher(tmp_path, gallery)
    local = publisher.enable(root, database_path=database)
    gallery.duplicate_on_publish = True

    result = publisher.publish(root, database_path=database)

    assert result.outcome is PublishOutcome.CONFLICTED
    assert publisher.enable(root, database_path=database) == local


def test_remote_lookup_retries_transient_failures(campaign, tmp_path):
    root, database = campaign
    gallery = MockGallery()
    gallery.failures = 2
    publisher = _publisher(tmp_path, gallery, retry_attempts=3)
    publisher.enable(root, database_path=database)

    assert publisher.publish(root, database_path=database).revision == 1


def test_unrelated_releases_do_not_affect_revision(campaign, tmp_path):
    root, database = campaign
    gallery = MockGallery()
    gallery.releases.append(SimpleNamespace(campaign_id="unrelated", revision=99))
    publisher = _publisher(tmp_path, gallery)
    publisher.enable(root, database_path=database)

    assert publisher.publish(root, database_path=database).revision == 1
