from pathlib import Path
import sys
import types
from uuid import uuid4

import pytest
import requests

if "cryptography.fernet" not in sys.modules:
    cryptography = types.ModuleType("cryptography")
    fernet = types.ModuleType("cryptography.fernet")
    fernet.Fernet = object
    fernet.InvalidToken = ValueError
    cryptography.fernet = fernet
    sys.modules["cryptography"] = cryptography
    sys.modules["cryptography.fernet"] = fernet

from modules.generic.github_gallery_client import GithubGalleryClient
from modules.generic.github_release_errors import describe_github_error


class FakeResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload
        self.text = ""

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code} response")


class FakeSession:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.posts = []

    def post(self, url, **kwargs):
        self.posts.append((url, kwargs))
        return next(self.responses)

    def get(self, _url, **_kwargs):
        return next(self.responses)

    def close(self):
        pass


def _manifest(campaign_id):
    return {
        "version": 1,
        "bundle_mode": "full_campaign",
        "sync": {
            "campaign_id": campaign_id,
            "revision": 1,
            "snapshot_sha256": "a" * 64,
            "snapshot_mode": "full_campaign",
        },
    }


def test_publish_resumes_matching_release_after_interrupted_asset_upload(tmp_path, monkeypatch):
    client = GithubGalleryClient(repo="owner/repo", token="token")
    archive = tmp_path / "campaign.zip"
    archive.write_bytes(b"zip")
    manifest = _manifest(str(uuid4()))
    metadata = client._metadata_from_manifest(manifest, "Campaign", "")
    release = {
        "id": 7,
        "tag_name": f"campaign-{manifest['sync']['campaign_id']}-r1",
        "name": "Campaign",
        "body": client._serialize_body(metadata),
        "upload_url": "https://uploads.example/releases/7/assets{?name}",
        "assets": [],
    }
    asset = {
        "id": 8,
        "name": archive.name,
        "browser_download_url": "https://example/campaign.zip",
        "size": 3,
    }
    session = FakeSession([FakeResponse(422, {"message": "Validation Failed"}), FakeResponse(200, release), FakeResponse(201, asset)])
    monkeypatch.setattr(client, "_create_session", lambda **_kwargs: session)

    result = client.publish_bundle(archive, manifest, title="Campaign")

    assert result.release_id == 7
    assert len(session.posts) == 2
    assert session.posts[1][0].startswith("https://uploads.example/releases/7/assets")


def test_publish_does_not_overwrite_existing_release_asset(tmp_path, monkeypatch):
    client = GithubGalleryClient(repo="owner/repo", token="token")
    archive = tmp_path / "campaign.zip"
    archive.write_bytes(b"zip")
    manifest = _manifest(str(uuid4()))
    metadata = client._metadata_from_manifest(manifest, "Campaign", "")
    release = {
        "body": client._serialize_body(metadata),
        "assets": [{"id": 1}],
        "upload_url": "https://uploads.example/assets{?name}",
    }
    session = FakeSession([FakeResponse(422, {}), FakeResponse(200, release)])
    monkeypatch.setattr(client, "_create_session", lambda **_kwargs: session)

    with pytest.raises(RuntimeError, match="already contains an archive"):
        client.publish_bundle(archive, manifest, title="Campaign")


def test_github_validation_details_are_readable():
    response = FakeResponse(422, {
        "message": "Validation Failed",
        "errors": [{"resource": "Release", "field": "tag_name", "code": "already_exists"}],
    })

    assert describe_github_error(response) == (
        "Validation Failed: Release tag_name already_exists"
    )
