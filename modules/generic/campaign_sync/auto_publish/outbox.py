"""Atomic JSON outbox with corrupt-file recovery and campaign coalescing."""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Iterable, Optional

from .models import OutboxEntry


class DurableOutbox:
    def __init__(self, path: Path) -> None:
        self.path = Path(path).expanduser()
        self._lock = threading.RLock()
        self._entries: dict[str, OutboxEntry] = {}
        self._load()

    def _load(self) -> None:
        with self._lock:
            if not self.path.exists():
                return
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
                entries = data.get("entries", data) if isinstance(data, dict) else data
                self._entries = {entry.campaign_id: entry for entry in map(OutboxEntry.from_dict, entries)}
            except (OSError, ValueError, TypeError, KeyError):
                # Preserve evidence for support while allowing startup to continue.
                recovery = self.path.with_suffix(self.path.suffix + ".corrupt")
                try:
                    os.replace(self.path, recovery)
                except OSError:
                    pass
                self._entries = {}

    def _persist(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_name(self.path.name + ".tmp")
        payload = {"version": 1, "entries": [e.to_dict() for e in self._entries.values()]}
        with temporary.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, self.path)

    def upsert(self, entry: OutboxEntry) -> OutboxEntry:
        with self._lock:
            previous = self._entries.get(entry.campaign_id)
            if previous is not None:
                entry = entry.updated(
                    first_dirty_at=min(previous.first_dirty_at, entry.first_dirty_at),
                    last_dirty_at=max(previous.last_dirty_at, entry.last_dirty_at),
                    retry_count=previous.retry_count,
                    next_attempt_at=previous.next_attempt_at,
                    failure_category=previous.failure_category,
                    failure_message=previous.failure_message,
                    force_full_checkpoint=(
                        previous.force_full_checkpoint or entry.force_full_checkpoint
                    ),
                )
            self._entries[entry.campaign_id] = entry
            self._persist()
            return entry

    def replace(self, entry: OutboxEntry) -> None:
        with self._lock:
            self._entries[entry.campaign_id] = entry
            self._persist()

    def remove(self, campaign_id: str) -> Optional[OutboxEntry]:
        with self._lock:
            value = self._entries.pop(campaign_id, None)
            if value is not None:
                self._persist()
            return value

    def get(self, campaign_id: str) -> Optional[OutboxEntry]:
        with self._lock:
            return self._entries.get(campaign_id)

    def entries(self) -> tuple[OutboxEntry, ...]:
        with self._lock:
            return tuple(self._entries.values())

    def due(self, now: float) -> Iterable[OutboxEntry]:
        return tuple(e for e in self.entries() if e.next_attempt_at <= now)
