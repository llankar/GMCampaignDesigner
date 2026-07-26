from pathlib import Path
from types import SimpleNamespace
import sqlite3
import zipfile
import json
import io

import pytest

from modules.generic.campaign_sync.metadata_store import InstallationStateStore
from modules.generic.campaign_sync.hashing import sha256_file
from modules.generic.campaign_sync.publisher import (
    CampaignPublisher,
    PublishOutcome,
    StaleParentError,
)


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


def test_release_digest_authenticates_archive_and_bundle_retains_uuid(campaign, tmp_path):
    root, database = campaign
    gallery = MockGallery()
    publisher = _publisher(tmp_path, gallery)
    identity = publisher.enable(root, database_path=database)

    result = publisher.publish(root, database_path=database)

    assert result.snapshot_sha256 == result.release.archive_sha256
    with zipfile.ZipFile(io.BytesIO(result.release.archive_bytes)) as archive:
        manifest = json.loads(archive.read("manifest.json"))
    assert manifest["sync"]["campaign_id"] == identity.campaign_id


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
