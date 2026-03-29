from __future__ import annotations

from time import perf_counter
from uuid import uuid4

from modules.core.ai import (
    EVENT_AI_PIPELINE_COMPLETED,
    EVENT_AI_PIPELINE_FAILED,
    EVENT_AI_PIPELINE_PHASE,
    EVENT_AI_PIPELINE_STARTED,
    normalize_local_ai_metadata,
    publish_local_ai_event,
)


class AIPipelineRunner:
    """Common wrapper around AI client calls with pipeline event emission."""

    def __init__(self, ai_client, pipeline_name: str, request_id: str | None = None) -> None:
        self.ai_client = ai_client
        self.pipeline_name = pipeline_name
        self.request_id = request_id or str(uuid4())

    def emit_phase(self, phase: str, message: str = "", **metadata) -> None:
        publish_local_ai_event(
            event_type=EVENT_AI_PIPELINE_PHASE,
            request_id=self.request_id,
            phase=phase,
            message=message,
            metadata=metadata,
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
        feature = context_metadata.get("feature") or self.pipeline_name
        request_prompt = self._extract_prompt_text(messages)
        model = chat_kwargs.get("model") or getattr(self.ai_client, "model", "")
        metadata = normalize_local_ai_metadata(
            context_metadata,
            feature=feature,
            prompt_text=request_prompt,
            model=model,
        )
        start_message = "AI pipeline started"
        if action_label:
            start_message = f"{action_label} started"
        prepare_message = "Preparing AI request"
        if action_label:
            prepare_message = f"Preparing request: {action_label}"
        effective_phase_message = phase_message or "Calling AI model"
        if action_label and phase_message == "Calling AI model":
            effective_phase_message = action_label

        publish_local_ai_event(
            event_type=EVENT_AI_PIPELINE_STARTED,
            request_id=self.request_id,
            phase="start",
            message=start_message,
            metadata=metadata,
        )
        self.emit_phase("prepare_request", prepare_message, **context_metadata)
        self.emit_phase(phase, effective_phase_message, **context_metadata)
        started = perf_counter()
        try:
            response = self.ai_client.chat(messages, **chat_kwargs)
        except Exception as exc:
            publish_local_ai_event(
                event_type=EVENT_AI_PIPELINE_FAILED,
                request_id=self.request_id,
                phase=phase,
                message=str(exc),
                is_terminal=True,
                metadata=metadata,
                duration_ms=int((perf_counter() - started) * 1000),
            )
            raise

        publish_local_ai_event(
            event_type=EVENT_AI_PIPELINE_COMPLETED,
            request_id=self.request_id,
            phase="completed",
            message="AI pipeline completed",
            is_terminal=True,
            metadata=metadata,
            response_text=response,
            duration_ms=int((perf_counter() - started) * 1000),
        )
        return response

    @staticmethod
    def _extract_prompt_text(messages) -> str:
        chunks: list[str] = []
        for message in messages or []:
            content = ""
            if isinstance(message, dict):
                content = str(message.get("content") or "")
            elif message is not None:
                content = str(message)
            if content:
                chunks.append(content.strip())
        return "\n\n".join(chunk for chunk in chunks if chunk).strip()


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
