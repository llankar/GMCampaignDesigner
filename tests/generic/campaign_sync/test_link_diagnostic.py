"""Diagnostics for campaign identities linked to GitHub releases."""

from types import SimpleNamespace
from uuid import uuid4

import pytest
from modules.generic.campaign_sync.metadata_store import CampaignSyncMetadataStore
from modules.generic.campaign_sync.models import CampaignSyncMetadata
from modules.generic.campaign_sync.publisher import (
    CampaignPublisher,
    CampaignSyncLinkState,
)


class DiagnosticGallery:
    repo = "guild/campaigns"

    def __init__(self, remote_revision=0, error=None):
        self.remote_revision = remote_revision
        self.error = error

    def highest_revision(self, campaign_id):
        if self.error:
            raise self.error
        if not self.remote_revision:
            return None
        return SimpleNamespace(campaign_id=campaign_id, revision=self.remote_revision)


def write_local_revision(root, revision):
    metadata = CampaignSyncMetadata(
        campaign_id=str(uuid4()),
        revision=revision,
        parent_revision=revision - 1,
        snapshot_sha256="a" * 64,
        published_at="2026-07-28T00:00:00Z",
        publisher_installation_id="installation",
        bundle_version=1,
    )
    CampaignSyncMetadataStore(root).write(metadata)
    return metadata


@pytest.mark.parametrize(
    ("local_revision", "remote_revision", "expected"),
    [
        (2, 0, CampaignSyncLinkState.ORPHANED_LOCAL_METADATA),
        (2, 2, CampaignSyncLinkState.MATCHED_REMOTE),
        (2, 3, CampaignSyncLinkState.REMOTE_AHEAD),
    ],
)
def test_diagnostic_compares_local_and_remote_revisions(
    tmp_path, local_revision, remote_revision, expected
):
    local = write_local_revision(tmp_path, local_revision)
    diagnostic = CampaignPublisher(
        DiagnosticGallery(remote_revision), retry_delay=0
    ).diagnose_link(tmp_path)

    assert diagnostic.state is expected
    assert diagnostic.repository == "guild/campaigns"
    assert diagnostic.campaign_id == local.campaign_id
    assert diagnostic.local_revision == local_revision
    assert diagnostic.remote_revision == remote_revision
    assert "Repository: guild/campaigns" in diagnostic.details()
    assert f"Campaign ID: {local.campaign_id}" in diagnostic.details()
    assert f"Local revision: {local_revision}" in diagnostic.details()
    assert f"Remote revision: {remote_revision}" in diagnostic.details()


def test_diagnostic_distinguishes_network_failure(tmp_path):
    write_local_revision(tmp_path, 2)
    diagnostic = CampaignPublisher(
        DiagnosticGallery(error=OSError("offline")), retry_delay=0
    ).diagnose_link(tmp_path)

    assert diagnostic.state is CampaignSyncLinkState.REMOTE_UNREACHABLE
    assert diagnostic.remote_revision is None
    assert "offline" in diagnostic.error


def test_diagnostic_reports_invalid_remote_metadata_as_unreachable(tmp_path):
    write_local_revision(tmp_path, 2)
    gallery = DiagnosticGallery(remote_revision="invalid")

    diagnostic = CampaignPublisher(gallery, retry_delay=0).diagnose_link(tmp_path)

    assert diagnostic.state is CampaignSyncLinkState.REMOTE_UNREACHABLE
    assert diagnostic.remote_revision is None
    assert "invalid revision metadata" in diagnostic.error


@pytest.mark.parametrize("status_code", [401, 403])
def test_diagnostic_distinguishes_invalid_credentials(tmp_path, status_code):
    write_local_revision(tmp_path, 2)
    error = RuntimeError("credentials rejected")
    error.response = SimpleNamespace(status_code=status_code)
    diagnostic = CampaignPublisher(
        DiagnosticGallery(error=error), retry_delay=0
    ).diagnose_link(tmp_path)

    assert diagnostic.state is CampaignSyncLinkState.INVALID_CREDENTIALS
    assert diagnostic.remote_revision is None


def test_diagnostic_identifies_new_unpublished_local_link(tmp_path):
    publisher = CampaignPublisher(DiagnosticGallery(), retry_delay=0)
    local = CampaignSyncMetadata(
        campaign_id=str(uuid4()), revision=1, parent_revision=None,
        snapshot_sha256="a" * 64, published_at="",
        publisher_installation_id="installation", bundle_version=1,
    )
    CampaignSyncMetadataStore(tmp_path).write(local)

    diagnostic = publisher.diagnose_link(tmp_path)

    assert local.revision == 1
    assert diagnostic.state is CampaignSyncLinkState.NEW_LOCAL_UNPUBLISHED
