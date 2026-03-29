from __future__ import annotations

from uuid import uuid4

from modules.core.ai import (
    AIPipelineEvent,
    EVENT_AI_PIPELINE_COMPLETED,
    EVENT_AI_PIPELINE_FAILED,
    EVENT_AI_PIPELINE_PHASE,
    EVENT_AI_PIPELINE_STARTED,
    ai_pipeline_events,
)


class AIPipelineRunner:
    """Common wrapper around AI client calls with pipeline event emission."""

    def __init__(self, ai_client, pipeline_name: str, request_id: str | None = None) -> None:
        self.ai_client = ai_client
        self.pipeline_name = pipeline_name
        self.request_id = request_id or str(uuid4())

    def emit_phase(self, phase: str, message: str = "", **metadata) -> None:
        ai_pipeline_events.emit(
            AIPipelineEvent(
                event_type=EVENT_AI_PIPELINE_PHASE,
                request_id=self.request_id,
                phase=phase,
                message=message,
                metadata={"pipeline": self.pipeline_name, **metadata},
            )
        )

    def run_chat(
        self,
        messages,
        *,
        phase: str = "llm_call",
        phase_message: str = "Calling AI model",
        **chat_kwargs,
    ):
        ai_pipeline_events.emit(
            AIPipelineEvent(
                event_type=EVENT_AI_PIPELINE_STARTED,
                request_id=self.request_id,
                phase="start",
                message="AI pipeline started",
                metadata={"pipeline": self.pipeline_name},
            )
        )
        self.emit_phase("prepare_request", "Preparing AI request")
        self.emit_phase(phase, phase_message)
        try:
            response = self.ai_client.chat(messages, **chat_kwargs)
        except Exception as exc:
            ai_pipeline_events.emit(
                AIPipelineEvent(
                    event_type=EVENT_AI_PIPELINE_FAILED,
                    request_id=self.request_id,
                    phase=phase,
                    message=str(exc),
                    is_terminal=True,
                    metadata={"pipeline": self.pipeline_name},
                )
            )
            raise

        ai_pipeline_events.emit(
            AIPipelineEvent(
                event_type=EVENT_AI_PIPELINE_COMPLETED,
                request_id=self.request_id,
                phase="completed",
                message="AI pipeline completed",
                is_terminal=True,
                metadata={"pipeline": self.pipeline_name},
            )
        )
        return response


def execute_ai_chat(
    ai_client,
    messages,
    *,
    pipeline_name: str,
    request_id: str | None = None,
    phase: str = "llm_call",
    phase_message: str = "Calling AI model",
    **chat_kwargs,
):
    runner = AIPipelineRunner(ai_client=ai_client, pipeline_name=pipeline_name, request_id=request_id)
    return runner.run_chat(
        messages,
        phase=phase,
        phase_message=phase_message,
        **chat_kwargs,
    )
