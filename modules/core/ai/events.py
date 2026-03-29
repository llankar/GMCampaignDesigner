from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Callable, DefaultDict


@dataclass(slots=True)
class AIPipelineEvent:
    event_type: str
    request_id: str
    phase: str = ""
    message: str = ""
    is_terminal: bool = False
    metadata: dict = field(default_factory=dict)


class AIPipelineEventBus:
    def __init__(self) -> None:
        self._subscribers: DefaultDict[str, list[Callable[[AIPipelineEvent], None]]] = defaultdict(list)

    def subscribe(self, event_type: str, callback: Callable[[AIPipelineEvent], None]) -> Callable[[], None]:
        self._subscribers[event_type].append(callback)

        def _unsubscribe() -> None:
            listeners = self._subscribers.get(event_type, [])
            if callback in listeners:
                listeners.remove(callback)

        return _unsubscribe

    def emit(self, event: AIPipelineEvent) -> None:
        for callback in list(self._subscribers.get(event.event_type, [])):
            callback(event)
        for callback in list(self._subscribers.get("*", [])):
            callback(event)


EVENT_AI_PIPELINE_STARTED = "ai.pipeline.started"
EVENT_AI_PIPELINE_PHASE = "ai.pipeline.phase"
EVENT_AI_PIPELINE_COMPLETED = "ai.pipeline.completed"
EVENT_AI_PIPELINE_FAILED = "ai.pipeline.failed"


ai_pipeline_events = AIPipelineEventBus()
