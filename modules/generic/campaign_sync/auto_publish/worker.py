"""Background publication worker; deliberately contains no UI dependencies."""

from __future__ import annotations

from queue import Queue
from typing import Callable

from modules.generic.campaign_sync.publisher import PublishOutcome

from .models import EventKind, PublicationJob, SyncState, WorkerEvent
from .retry import FailureCategory, classify_failure


class PublicationWorker:
    """Execute one immutable job and emit ordered immutable events."""

    def __init__(self, publisher_factory: Callable[[], object], events: Queue) -> None:
        self.publisher_factory = publisher_factory
        self.events = events

    def run(self, job: PublicationJob) -> None:
        sequence = 0
        terminal = False

        def emit(kind, state, message="", progress=None, result=None, category=None, *, final=False):
            nonlocal sequence, terminal
            if terminal:
                return
            sequence += 1
            terminal = final
            self.events.put(WorkerEvent(
                job.job_id, job.campaign_id, sequence, kind, state, message,
                progress, result, category.value if category else None, final,
            ))

        emit(EventKind.STATE, SyncState.PREPARING, "Preparing campaign snapshot", 0.0)

        def progress(message: str, fraction: float) -> None:
            state = SyncState.UPLOADING if float(fraction) >= 0.5 else SyncState.PREPARING
            emit(EventKind.PROGRESS, state, message, max(0.0, min(1.0, float(fraction))))

        try:
            publisher = self.publisher_factory()
            result = publisher.publish(
                job.campaign_root, database_path=job.database_path,
                title=job.title, description=job.summary,
                change_summary=job.summary, progress_callback=progress,
            )
            if result.outcome is PublishOutcome.CONFLICTED:
                emit(EventKind.CONFLICT, SyncState.CONFLICT,
                     result.conflict_message or "Remote revision conflict", result=result,
                     category=FailureCategory.CONFLICT, final=True)
            else:
                emit(EventKind.SUCCESS, SyncState.SYNCHRONIZED,
                     f"Revision {result.revision} published", 1.0, result, final=True)
        except BaseException as error:  # worker boundary must always produce a terminal event
            category = classify_failure(error)
            state = {
                FailureCategory.CONFLICT: SyncState.CONFLICT,
                FailureCategory.CREDENTIALS: SyncState.AUTH_REQUIRED,
                FailureCategory.AUTHENTICATION: SyncState.AUTH_REQUIRED,
            }.get(category, SyncState.FAILED)
            kind = EventKind.CONFLICT if category is FailureCategory.CONFLICT else EventKind.FAILURE
            emit(kind, state, str(error), category=category, final=True)
