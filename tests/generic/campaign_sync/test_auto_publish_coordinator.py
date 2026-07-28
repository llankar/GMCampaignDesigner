from queue import Queue

from modules.generic.campaign_sync.auto_publish.coordinator import AutoPublishCoordinator


class MemoryOutbox:
    def entries(self):
        return []


class IdleWorker:
    def __init__(self):
        self.events = Queue()


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
