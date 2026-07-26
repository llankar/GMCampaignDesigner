from uuid import uuid4

from modules.generic.campaign_sync.metadata_store import (
    CampaignSyncMetadataStore,
    InstallationStateStore,
)
from modules.generic.campaign_sync.models import CampaignSyncMetadata


def test_campaign_identity_persists_in_campaign_local_store(tmp_path):
    store = CampaignSyncMetadataStore(tmp_path)
    campaign_id = str(uuid4())
    metadata = CampaignSyncMetadata(
        campaign_id=campaign_id, revision=1, parent_revision=None,
        snapshot_sha256="f" * 64, published_at="now",
        publisher_installation_id="installation", bundle_version=1,
    )
    store.write(metadata)

    assert store.read() == metadata
    assert store.path == tmp_path / ".gmcd" / "sync.json"


def test_machine_state_is_separate_from_campaign(tmp_path):
    local = InstallationStateStore(tmp_path / "machine" / "installation.json")
    first = local.installation_id()
    assert local.installation_id() == first
