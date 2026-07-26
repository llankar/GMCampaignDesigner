from uuid import uuid4

import pytest

from modules.generic.campaign_sync.models import CampaignSyncMetadata, RemoteCampaignRevision


def test_revision_round_trip_preserves_sync_fields():
    metadata = CampaignSyncMetadata(
        campaign_id=str(uuid4()),
        revision=3,
        parent_revision=2,
        snapshot_sha256="a" * 64,
        published_at="2026-07-26T12:00:00Z",
        publisher_installation_id=str(uuid4()),
        bundle_version=1,
        change_summary="New encounter",
    )

    assert CampaignSyncMetadata.from_dict(metadata.to_dict()) == metadata


def test_revision_rejects_non_monotonic_parent():
    with pytest.raises(ValueError):
        CampaignSyncMetadata(
            campaign_id=str(uuid4()), revision=2, parent_revision=2,
            snapshot_sha256="", published_at="", publisher_installation_id="x",
            bundle_version=1,
        )


def test_remote_revision_rejects_non_monotonic_parent():
    with pytest.raises(ValueError, match="parent_revision"):
        RemoteCampaignRevision(
            campaign_id=str(uuid4()), revision=3, parent_revision=3,
            snapshot_sha256="a" * 64, snapshot_mode="full_campaign",
        )


def test_remote_revision_requires_a_valid_snapshot_digest():
    with pytest.raises(ValueError, match="snapshot_sha256"):
        RemoteCampaignRevision(
            campaign_id=str(uuid4()), revision=1, parent_revision=None,
            snapshot_sha256="", snapshot_mode="full_campaign",
        )
