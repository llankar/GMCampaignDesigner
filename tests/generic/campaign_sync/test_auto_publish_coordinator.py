from queue import Queue
from pathlib import Path

from modules.generic.campaign_sync.auto_publish.coordinator import AutoPublishCoordinator
from modules.generic.campaign_sync.auto_publish.models import OutboxEntry, PublicationJob
from modules.generic.campaign_sync.auto_publish.worker import PublicationWorker
from modules.generic.campaign_sync.change_detector import CampaignChangeResult, CampaignChangeState
from modules.generic.campaign_sync.publisher import PublishOutcome


class MemoryOutbox:
    def entries(self):
        return []


class IdleWorker:
    def __init__(self):
        self.events = Queue()


class ImmediateExecutor:
    def submit(self, function, *args):
        function(*args)


def test_configure_applies_saved_preferences_without_restart():
    coordinator = AutoPublishCoordinator(MemoryOutbox(), IdleWorker())
    try:
        coordinator.configure(
            automatic=False,
            offline=True,
            idle_delay=12,
            maximum_interval=90,
        )

        assert coordinator.automatic is False
        assert coordinator.offline is True
        assert coordinator.scheduler.idle_delay == 12
        assert coordinator.scheduler.maximum_interval == 90
    finally:
        coordinator.shutdown()


def test_explicit_publication_bypasses_offline_background_preference():
    jobs = []

    class Outbox:
        def __init__(self):
            self.entry = OutboxEntry(
                "campaign", "Campaign", Path("/campaign"),
                Path("/campaign/campaign.db"), 7, 1.0, 2.0,
            )

        def get(self, campaign_id):
            return self.entry if campaign_id == self.entry.campaign_id else None

        def entries(self):
            return [self.entry]

    class Detector:
        def detect(self, *_args, **_kwargs):
            return CampaignChangeResult(
                CampaignChangeState.LOCALLY_MODIFIED, "current-fingerprint"
            )

    class Worker(IdleWorker):
        def run(self, job):
            jobs.append(job)

    coordinator = AutoPublishCoordinator(
        Outbox(), Worker(), detector=Detector(), offline=True,
        executor=ImmediateExecutor(),
    )

    # Offline mode must continue to suppress unattended publication while an
    # explicit user action remains available.
    coordinator.tick()
    assert jobs == []

    assert coordinator.publish_now("campaign") is True
    assert len(jobs) == 1
    assert jobs[0].campaign_id == "campaign"


def test_worker_preserves_forced_full_checkpoint_option():
    calls = []

    class Publisher:
        def publish(self, *args, **kwargs):
            calls.append(kwargs)
            return type("Result", (), {"outcome": PublishOutcome.PUBLISHED, "revision": 8})()

    worker = PublicationWorker(Publisher, Queue())
    worker.run(PublicationJob(
        "job", "campaign", "Campaign", Path("/campaign"), Path("/campaign/campaign.db"),
        7, 1.0, 2.0, "Campaign — Revision 8", "summary",
        force_full_checkpoint=True,
    ))

    assert calls[0]["force_full_checkpoint"] is True


def test_clean_campaign_can_still_dispatch_requested_full_checkpoint():
    jobs = []

    class Outbox:
        def remove(self, _campaign_id):
            raise AssertionError("forced checkpoint was silently treated as a no-op")

    class Detector:
        def detect(self, *_args, **_kwargs):
            return CampaignChangeResult(CampaignChangeState.CLEAN, "current-fingerprint")

    class Worker(IdleWorker):
        def run(self, job):
            jobs.append(job)

    coordinator = AutoPublishCoordinator(Outbox(), Worker(), detector=Detector())
    try:
        coordinator._prepare_and_run(
            OutboxEntry(
                "campaign", "Campaign", Path("/campaign"), Path("/campaign/campaign.db"),
                7, 1.0, 2.0, force_full_checkpoint=True,
            ),
            force=True,
        )
    finally:
        coordinator.shutdown()

    assert len(jobs) == 1
    assert jobs[0].force_full_checkpoint is True
