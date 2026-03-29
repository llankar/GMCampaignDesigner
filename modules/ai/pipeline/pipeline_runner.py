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
        context_metadata: dict | None = None,
        **chat_kwargs,
    ):
        context_metadata = context_metadata or {}
        action_label = str(context_metadata.get("action_label") or "").strip()
        metadata = {"pipeline": self.pipeline_name, **context_metadata}
        start_message = "AI pipeline started"
        if action_label:
            start_message = f"{action_label} started"
        prepare_message = "Preparing AI request"
        if action_label:
            prepare_message = f"Preparing request: {action_label}"
        effective_phase_message = phase_message or "Calling AI model"
        if action_label and phase_message == "Calling AI model":
            effective_phase_message = action_label

        ai_pipeline_events.emit(
            AIPipelineEvent(
                event_type=EVENT_AI_PIPELINE_STARTED,
                request_id=self.request_id,
                phase="start",
                message=start_message,
                metadata=metadata,
            )
        )
        self.emit_phase("prepare_request", prepare_message, **context_metadata)
        self.emit_phase(phase, effective_phase_message, **context_metadata)
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
                    metadata=metadata,
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
                metadata=metadata,
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
    context_metadata: dict | None = None,
    **chat_kwargs,
):
    runner = AIPipelineRunner(ai_client=ai_client, pipeline_name=pipeline_name, request_id=request_id)
    return runner.run_chat(
        messages,
        phase=phase,
        phase_message=phase_message,
        context_metadata=context_metadata,
        **chat_kwargs,
    )
