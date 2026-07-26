from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

from modules.generic.campaign_sync.metadata_store import (
    CampaignSyncMetadataStore,
    InstallationStateStore,
)
from modules.generic.campaign_sync.models import CampaignSyncMetadata
from modules.generic.campaign_sync.update_checker import (
    CampaignUpdateChecker,
    UpdateCheckSettings,
    UpdateStatus,
)


def _link(root, campaign_id, revision=2):
    CampaignSyncMetadataStore(root).write(CampaignSyncMetadata(
        campaign_id=campaign_id, revision=revision, parent_revision=revision - 1,
        snapshot_sha256="a" * 64, published_at="2026-01-01T00:00:00Z",
        publisher_installation_id="publisher", bundle_version=1,
    ))


def _release(campaign_id, revision, *, name="Remote", summary="New scenes"):
    return SimpleNamespace(
        release_id=1, asset_id=2, release_name=name, tag="tag",
        asset_name="campaign.zip", download_url="https://example/campaign.zip",
        published_at=datetime(2026, 7, 1, tzinfo=timezone.utc), author="alice",
        metadata={"sync": {"change_summary": summary}},
        campaign_id=campaign_id, revision=revision,
    )


class Gallery:
    def __init__(self, releases=None, error=None):
        self.releases = list(releases or [])
        self.error = error
        self.calls = []

    def highest_revision(self, campaign_id):
        self.calls.append(campaign_id)
        if self.error:
            raise self.error
        matches = [item for item in self.releases if item.campaign_id == campaign_id]
        return max(matches, key=lambda item: item.revision, default=None)


def _checker(tmp_path, gallery, now=None):
    return CampaignUpdateChecker(
        gallery,
        installation_store=InstallationStateStore(tmp_path / "installation.json"),
        clock=lambda: now or datetime(2026, 7, 26, tzinfo=timezone.utc),
    )


def test_unlinked_campaign_never_calls_gallery(tmp_path):
    gallery = Gallery()
    result = _checker(tmp_path, gallery).check(tmp_path / "campaign")
    assert result.status is UpdateStatus.UNLINKED
    assert gallery.calls == []


def test_unlinked_campaign_remains_unlinked_when_checks_are_disabled(tmp_path):
    gallery = Gallery()
    result = _checker(tmp_path, gallery).check(
        tmp_path / "campaign", UpdateCheckSettings(enabled=False, offline=True)
    )
    assert result.status is UpdateStatus.UNLINKED
    assert gallery.calls == []


def test_offline_operation_never_calls_gallery(tmp_path):
    campaign_id = str(uuid4())
    _link(tmp_path / "campaign", campaign_id)
    gallery = Gallery(error=OSError("offline"))
    result = _checker(tmp_path, gallery).check(
        tmp_path / "campaign", UpdateCheckSettings(offline=True)
    )
    assert result.status is UpdateStatus.OFFLINE
    assert gallery.calls == []


def test_network_failure_is_offline(tmp_path):
    campaign_id = str(uuid4())
    _link(tmp_path / "campaign", campaign_id)
    result = _checker(tmp_path, Gallery(error=OSError("no network"))).check(tmp_path / "campaign")
    assert result.status is UpdateStatus.OFFLINE


def test_malformed_local_metadata_is_invalid(tmp_path):
    sync = tmp_path / "campaign" / ".gmcd" / "sync.json"
    sync.parent.mkdir(parents=True)
    sync.write_text('{"campaign_id":"bad","revision":"name"}', encoding="utf-8")
    assert _checker(tmp_path, Gallery()).check(tmp_path / "campaign").status is UpdateStatus.REMOTE_INVALID


def test_numeric_string_local_revision_is_not_coerced(tmp_path):
    campaign_id = str(uuid4())
    sync = tmp_path / "campaign" / ".gmcd" / "sync.json"
    sync.parent.mkdir(parents=True)
    sync.write_text(
        '{"campaign_id":"%s","revision":"2","parent_revision":1,'
        '"snapshot_sha256":"%s"}' % (campaign_id, "a" * 64),
        encoding="utf-8",
    )
    assert _checker(tmp_path, Gallery()).check(tmp_path / "campaign").status is UpdateStatus.REMOTE_INVALID


def test_malformed_remote_revision_is_invalid(tmp_path):
    campaign_id = str(uuid4())
    root = tmp_path / "campaign"
    _link(root, campaign_id)
    remote = _release(campaign_id, 3)
    remote.revision = "3"
    assert _checker(tmp_path, Gallery([remote])).check(root).status is UpdateStatus.REMOTE_INVALID


def test_ignored_revision_is_local_and_suppressed(tmp_path):
    campaign_id = str(uuid4())
    root = tmp_path / "campaign"
    _link(root, campaign_id)
    checker = _checker(tmp_path, Gallery([_release(campaign_id, 3)]))
    checker.ignore_revision(root, 3)
    result = checker.check(root)
    assert result.status is UpdateStatus.UP_TO_DATE
    assert result.ignored is True
    assert not (root / ".gmcd" / "installation.json").exists()


def test_unrelated_release_is_not_selected(tmp_path):
    campaign_id = str(uuid4())
    root = tmp_path / "campaign"
    _link(root, campaign_id)
    result = _checker(tmp_path, Gallery([_release(str(uuid4()), 99)])).check(root)
    assert result.status is UpdateStatus.UP_TO_DATE


def test_newer_release_after_switching_campaigns(tmp_path):
    first_id, second_id = str(uuid4()), str(uuid4())
    first, second = tmp_path / "first", tmp_path / "second"
    _link(first, first_id, 4)
    _link(second, second_id, 1)
    gallery = Gallery([_release(first_id, 4), _release(second_id, 2)])
    checker = _checker(tmp_path, gallery)
    assert checker.check(first).status is UpdateStatus.UP_TO_DATE
    switched = checker.check(second)
    assert switched.status is UpdateStatus.UPDATE_AVAILABLE
    assert switched.installed_revision == 1
    assert switched.available_revision == 2
    assert gallery.calls == [first_id, second_id]


def test_check_interval_uses_per_installation_timestamp(tmp_path):
    campaign_id = str(uuid4())
    root = tmp_path / "campaign"
    _link(root, campaign_id)
    now = datetime(2026, 7, 26, tzinfo=timezone.utc)
    gallery = Gallery([_release(campaign_id, 2)])
    checker = _checker(tmp_path, gallery, now)
    assert checker.check(root).checked_remote
    second = checker.check(root, UpdateCheckSettings(interval_seconds=int(timedelta(days=1).total_seconds())))
    assert not second.checked_remote
    assert len(gallery.calls) == 1
