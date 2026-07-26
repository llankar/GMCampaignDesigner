from datetime import datetime, timezone
import sys
import types
from uuid import uuid4

if "cryptography.fernet" not in sys.modules:
    cryptography = types.ModuleType("cryptography")
    fernet = types.ModuleType("cryptography.fernet")
    fernet.Fernet = object
    fernet.InvalidToken = ValueError
    cryptography.fernet = fernet
    sys.modules["cryptography"] = cryptography
    sys.modules["cryptography.fernet"] = fernet

from modules.generic.github_gallery_client import GalleryBundleSummary, GithubGalleryClient


def _summary(campaign_id, revision, name="Same name"):
    return GalleryBundleSummary(
        1, 2, name, "tag", "bundle.zip", "https://example/bundle.zip", 10,
        datetime.now(timezone.utc), "author", "", {}, name, "", {}, "", False,
        1, 0, campaign_id=campaign_id, revision=revision,
    )


def test_highest_revision_uses_campaign_id_not_display_name(monkeypatch):
    wanted, unrelated = str(uuid4()), str(uuid4())
    client = GithubGalleryClient(repo="owner/repo")
    monkeypatch.setattr(client, "list_bundles", lambda **kwargs: [
        _summary(wanted, 2), _summary(unrelated, 99), _summary(wanted, 4)
    ])
    assert client.highest_revision(wanted).revision == 4


def test_highest_revision_normalizes_campaign_uuid(monkeypatch):
    wanted = str(uuid4())
    client = GithubGalleryClient(repo="owner/repo")
    monkeypatch.setattr(client, "list_bundles", lambda **kwargs: [_summary(wanted, 3)])

    assert client.highest_revision(wanted.upper()).revision == 3


def test_old_manifest_is_manual_non_synchronized_bundle():
    client = GithubGalleryClient(repo="owner/repo")
    metadata = client._metadata_from_manifest({"version": 1, "entities": {}}, "Old", "")
    summary = client._build_summary(
        {"id": 1, "name": "Old", "assets": [{}]},
        {"id": 2, "name": "old.zip", "browser_download_url": "https://example/old.zip"},
        metadata,
    )
    assert summary.campaign_id is None
    assert summary.revision is None


def test_malformed_sync_metadata_is_manual_non_synchronized_bundle():
    client = GithubGalleryClient(repo="owner/repo")
    metadata = {"sync": {"campaign_id": "not-a-uuid", "revision": -1}}
    summary = client._build_summary(
        {"id": 1, "name": "Manual", "assets": [{}]},
        {"id": 2, "name": "manual.zip", "browser_download_url": "https://example/manual.zip"},
        metadata,
    )

    assert summary.campaign_id is None
    assert summary.revision is None


def test_sync_metadata_without_digest_is_manual_non_synchronized_bundle():
    client = GithubGalleryClient(repo="owner/repo")
    metadata = {
        "sync": {
            "campaign_id": str(uuid4()),
            "revision": 1,
            "snapshot_mode": "full_campaign",
        }
    }
    summary = client._build_summary(
        {"id": 1, "name": "Manual", "assets": [{}]},
        {"id": 2, "name": "manual.zip", "browser_download_url": "https://example/manual.zip"},
        metadata,
    )

    assert summary.campaign_id is None
    assert summary.revision is None
