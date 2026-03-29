from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field
from time import perf_counter
from typing import Any, Callable, DefaultDict


@dataclass(slots=True)
class AIPipelineEvent:
    event_type: str
    request_id: str
    phase: str = ""
    message: str = ""
    is_terminal: bool = False
    metadata: dict = field(default_factory=dict)


class AIPipelineEventBus:
    LOCAL_AI_STEP_BUFFER_SIZE = 12

    def __init__(self) -> None:
        self._subscribers: DefaultDict[str, list[Callable[[AIPipelineEvent], None]]] = defaultdict(list)
        self._recent_local_ai_steps_by_request: dict[str, deque[dict[str, Any]]] = {}
        self._last_request_id = ""

    def subscribe(self, event_type: str, callback: Callable[[AIPipelineEvent], None]) -> Callable[[], None]:
        self._subscribers[event_type].append(callback)

        def _unsubscribe() -> None:
            listeners = self._subscribers.get(event_type, [])
            if callback in listeners:
                listeners.remove(callback)

        return _unsubscribe

    def emit(self, event: AIPipelineEvent) -> None:
        self._track_local_ai_metadata(event)
        for callback in list(self._subscribers.get(event.event_type, [])):
            callback(event)
        for callback in list(self._subscribers.get("*", [])):
            callback(event)

    def get_recent_local_ai_steps(self, request_id: str | None = None) -> list[dict[str, Any]]:
        target_request_id = request_id or self._last_request_id
        if not target_request_id:
            return []
        buffered = self._recent_local_ai_steps_by_request.get(target_request_id)
        return list(buffered or [])

    def _track_local_ai_metadata(self, event: AIPipelineEvent) -> None:
        metadata = normalize_local_ai_metadata(event.metadata)
        if not metadata.get("feature"):
            return

        if event.event_type == EVENT_AI_PIPELINE_STARTED and event.request_id != self._last_request_id:
            self._recent_local_ai_steps_by_request = {}

        self._last_request_id = event.request_id
        request_buffer = self._recent_local_ai_steps_by_request.setdefault(
            event.request_id, deque(maxlen=self.LOCAL_AI_STEP_BUFFER_SIZE)
        )
        request_buffer.append(
            {
                "event_type": event.event_type,
                "phase": event.phase,
                "message": event.message,
                "metadata": metadata,
            }
        )


EVENT_AI_PIPELINE_STARTED = "ai.pipeline.started"
EVENT_AI_PIPELINE_PHASE = "ai.pipeline.phase"
EVENT_AI_PIPELINE_COMPLETED = "ai.pipeline.completed"
EVENT_AI_PIPELINE_FAILED = "ai.pipeline.failed"


ai_pipeline_events = AIPipelineEventBus()


LOCAL_AI_METADATA_KEYS = ("prompt_text", "response_text", "model", "duration_ms", "feature")


def normalize_local_ai_metadata(metadata: dict | None = None, **overrides: Any) -> dict[str, Any]:
    source: dict[str, Any] = dict(metadata or {})
    source.update(overrides)
    normalized = {key: source.get(key) for key in LOCAL_AI_METADATA_KEYS}
    if normalized.get("duration_ms") is not None:
        try:
            normalized["duration_ms"] = int(float(normalized["duration_ms"]))
        except (TypeError, ValueError):
            normalized["duration_ms"] = None
    return normalized


def publish_local_ai_event(
    *,
    event_type: str,
    request_id: str,
    phase: str = "",
    message: str = "",
    is_terminal: bool = False,
    metadata: dict | None = None,
    **metadata_overrides: Any,
) -> None:
    ai_pipeline_events.emit(
        AIPipelineEvent(
            event_type=event_type,
            request_id=request_id,
            phase=phase,
            message=message,
            is_terminal=is_terminal,
            metadata=normalize_local_ai_metadata(metadata, **metadata_overrides),
        )
    )


def timed_local_ai_chat(
    chat_callable: Callable[[], str],
    *,
    metadata: dict | None = None,
    **metadata_overrides: Any,
) -> tuple[str, dict[str, Any]]:
    start = perf_counter()
    response_text = chat_callable()
    duration_ms = int((perf_counter() - start) * 1000)
    return response_text, normalize_local_ai_metadata(
        metadata,
        response_text=response_text,
        duration_ms=duration_ms,
        **metadata_overrides,
    )
