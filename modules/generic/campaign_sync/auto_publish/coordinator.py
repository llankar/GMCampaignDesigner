"""Thread-safe lifecycle, dirty state, serialization, and durable retries."""

from __future__ import annotations

import queue
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Callable, Optional
from uuid import uuid4

from modules.generic.campaign_sync.change_detector import CampaignChangeDetector, CampaignChangeState

from .models import EventKind, OutboxEntry, PublicationJob, SyncState, WorkerEvent
from .outbox import DurableOutbox
from .retry import FailureCategory, RetryPolicy
from .scheduler import PublicationScheduler


class AutoPublishCoordinator:
    """Managed publication service independent from the currently selected campaign."""

    def __init__(
        self, outbox: DurableOutbox, worker, *, detector: Optional[CampaignChangeDetector] = None,
        scheduler: Optional[PublicationScheduler] = None, retry_policy: Optional[RetryPolicy] = None,
        clock: Callable[[], float] = time.time, automatic: bool = True, offline: bool = False,
        executor=None,
    ) -> None:
        self.outbox, self.worker = outbox, worker
        self.detector = detector or CampaignChangeDetector()
        self.scheduler = scheduler or PublicationScheduler()
        self.retry_policy = retry_policy or RetryPolicy()
        self.clock, self.automatic, self.offline = clock, automatic, offline
        self.events: queue.Queue[WorkerEvent] = worker.events
        self._executor = executor or ThreadPoolExecutor(max_workers=3, thread_name_prefix="campaign-publish")
        self._owns_executor = executor is None
        self._lock = threading.RLock()
        self._inflight: set[str] = set()
        self._dirty_during_flight: set[str] = set()
        self._stopped = False

    def mark_dirty(self, *, campaign_id: str, campaign_name: str, campaign_root: Path,
                   database_path: Path, expected_parent_revision: int, when: Optional[float] = None) -> None:
        """Record a *successfully saved* campaign mutation."""
        now = self.clock() if when is None else when
        with self._lock:
            previous = self.outbox.get(campaign_id)
            first = previous.first_dirty_at if previous else now
            self.outbox.upsert(OutboxEntry(
                campaign_id, campaign_name, Path(campaign_root).resolve(), Path(database_path).resolve(),
                expected_parent_revision, first, now,
            ))
            if campaign_id in self._inflight:
                self._dirty_during_flight.add(campaign_id)

    def publish_now(self, campaign_id: str) -> bool:
        return self._dispatch(campaign_id, force=True)

    def tick(self) -> None:
        if self._stopped:
            return
        self._drain_terminals()
        if self.offline:
            return
        now = self.clock()
        for entry in self.outbox.entries():
            if entry.failure_category in {
                FailureCategory.CREDENTIALS.value, FailureCategory.AUTHENTICATION.value,
                FailureCategory.CONFIGURATION.value, FailureCategory.CONFLICT.value,
            }:
                continue
            if entry.next_attempt_at > now:
                continue
            if self.automatic and self.scheduler.is_due(entry.first_dirty_at, entry.last_dirty_at, now):
                self._dispatch(entry.campaign_id)

    def set_offline(self, value: bool) -> None:
        self.offline = bool(value)

    def configure(self, *, automatic: bool, offline: bool,
                  idle_delay: float, maximum_interval: float) -> None:
        """Apply publication preferences without requiring an application restart."""
        scheduler = PublicationScheduler(idle_delay, maximum_interval)
        with self._lock:
            self.automatic = bool(automatic)
            self.offline = bool(offline)
            self.scheduler = scheduler

    def credentials_changed(self) -> None:
        for entry in self.outbox.entries():
            if entry.failure_category in (FailureCategory.CREDENTIALS.value, FailureCategory.AUTHENTICATION.value):
                self.outbox.replace(entry.updated(failure_category=None, failure_message=None, next_attempt_at=0))

    def retry(self, campaign_id: str) -> bool:
        entry = self.outbox.get(campaign_id)
        if not entry:
            return False
        self.outbox.replace(entry.updated(failure_category=None, failure_message=None, next_attempt_at=0))
        return self._dispatch(campaign_id, force=True)

    def _dispatch(self, campaign_id: str, force: bool = False) -> bool:
        with self._lock:
            if self._stopped or self.offline or campaign_id in self._inflight:
                return False
            entry = self.outbox.get(campaign_id)
            if entry is None:
                return False
            # Fingerprinting is expensive and therefore submitted as part of dispatch work.
            self._inflight.add(campaign_id)
            self._executor.submit(self._prepare_and_run, entry, force)
            return True

    def _prepare_and_run(self, entry: OutboxEntry, force: bool) -> None:
        try:
            detected = self.detector.detect(entry.campaign_root, database_path=entry.database_path)
            if detected.state is CampaignChangeState.CLEAN:
                self.outbox.remove(entry.campaign_id)
                self.events.put(WorkerEvent(str(uuid4()), entry.campaign_id, 1, EventKind.SUCCESS,
                                            SyncState.SYNCHRONIZED, "No changes to publish", 1.0,
                                            terminal=True))
                return
            if detected.state is not CampaignChangeState.LOCALLY_MODIFIED:
                raise RuntimeError(detected.error or "Campaign change state is unknown")
            revision = entry.expected_parent_revision + 1
            title = f"{entry.campaign_name} — Revision {revision}"
            summary = (f"Changes saved between {entry.first_dirty_at:.0f} and "
                       f"{entry.last_dirty_at:.0f}; content fingerprint {detected.current_fingerprint[:12]}.")
            job = PublicationJob(
                str(uuid4()), entry.campaign_id, entry.campaign_name, entry.campaign_root,
                entry.database_path, entry.expected_parent_revision, entry.first_dirty_at,
                entry.last_dirty_at, title, summary, detected.current_fingerprint,
            )
            self.worker.run(job)
        except BaseException as error:
            self.events.put(WorkerEvent(str(uuid4()), entry.campaign_id, 1, EventKind.FAILURE,
                                        SyncState.FAILED, str(error), terminal=True))

    def _drain_terminals(self) -> None:
        # Preserve UI events: inspect terminal events via a side queue populated by bridge callback.
        return

    def handle_event(self, event: WorkerEvent) -> None:
        """Apply durable state changes; call from the main-thread event bridge."""
        if not event.terminal:
            return
        with self._lock:
            self._inflight.discard(event.campaign_id)
            entry = self.outbox.get(event.campaign_id)
            if entry is None:
                self._dirty_during_flight.discard(event.campaign_id)
                return
            follow_up = event.campaign_id in self._dirty_during_flight
            self._dirty_during_flight.discard(event.campaign_id)
            if event.kind is EventKind.SUCCESS:
                if follow_up:
                    self.outbox.replace(entry.updated(first_dirty_at=entry.last_dirty_at,
                                                      retry_count=0, next_attempt_at=0,
                                                      failure_category=None, failure_message=None))
                else:
                    self.outbox.remove(event.campaign_id)
            else:
                category = FailureCategory(event.failure_category or FailureCategory.PERMANENT.value)
                retry_count = entry.retry_count + 1
                next_attempt = 0.0
                if self.retry_policy.should_retry(category, retry_count):
                    next_attempt = self.clock() + self.retry_policy.delay(retry_count - 1)
                self.outbox.replace(entry.updated(retry_count=retry_count, next_attempt_at=next_attempt,
                                                  failure_category=category.value,
                                                  failure_message=event.message))

    def shutdown(self, wait: bool = False) -> None:
        self._stopped = True
        if self._owns_executor:
            self._executor.shutdown(wait=wait, cancel_futures=True)
