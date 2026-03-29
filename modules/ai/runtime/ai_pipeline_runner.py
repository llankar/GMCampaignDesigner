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
    """Common runtime wrapper for LocalAIClient.chat calls and pipeline events."""

    def __init__(self, ai_client, pipeline_name: str, request_id: str | None = None) -> None:
        self.ai_client = ai_client
        self.pipeline_name = pipeline_name
        self.request_id = request_id or str(uuid4())

    @staticmethod
    def serialize_prompt(messages) -> str:
        """Serialize the exact conversation payload sent to the model."""
        lines: list[str] = []
        for idx, message in enumerate(messages or [], start=1):
            if isinstance(message, dict):
                role = str(message.get("role") or "unknown").strip() or "unknown"
                content = str(message.get("content") or "")
            else:
                role = "message"
                content = "" if message is None else str(message)
            content = content.strip()
            if content:
                lines.append(f"[{idx}:{role}]\n{content}")
            else:
                lines.append(f"[{idx}:{role}]")
        return "\n\n".join(lines).strip()


    def chat_once(self, messages, **chat_kwargs):
        """Call the model once and return raw response + normalized metadata."""
        started = perf_counter()
        prompt_text = self.serialize_prompt(messages)
        model = chat_kwargs.get("model") or getattr(self.ai_client, "model", "")
        response_text = self.ai_client.chat(messages, **chat_kwargs)
        metadata = normalize_local_ai_metadata(
            {
                "feature": self.pipeline_name,
                "prompt_text": prompt_text,
                "response_text": response_text,
                "model": model,
                "duration_ms": int((perf_counter() - started) * 1000),
            }
        )
        return response_text, metadata

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
        prompt_text = self.serialize_prompt(messages)
        model = chat_kwargs.get("model") or getattr(self.ai_client, "model", "")
        metadata = normalize_local_ai_metadata(
            context_metadata,
            feature=feature,
            prompt_text=prompt_text,
            model=model,
        )

        start_message = f"{action_label} started" if action_label else "AI pipeline started"
        prepare_message = f"Preparing request: {action_label}" if action_label else "Preparing AI request"
        effective_phase_message = phase_message or "Calling AI model"
        if action_label and effective_phase_message == "Calling AI model":
            effective_phase_message = action_label

        publish_local_ai_event(
            event_type=EVENT_AI_PIPELINE_STARTED,
            request_id=self.request_id,
            phase="start",
            message=start_message,
            metadata=metadata,
        )
        self.emit_phase("prepare_request", prepare_message, **metadata)
        self.emit_phase(phase, effective_phase_message, **metadata)

        started = perf_counter()
        try:
            response_text = self.ai_client.chat(messages, **chat_kwargs)
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

        completed_metadata = normalize_local_ai_metadata(
            metadata,
            response_text=response_text,
            duration_ms=int((perf_counter() - started) * 1000),
        )
        publish_local_ai_event(
            event_type=EVENT_AI_PIPELINE_COMPLETED,
            request_id=self.request_id,
            phase="completed",
            message="AI pipeline completed",
            is_terminal=True,
            metadata=completed_metadata,
        )
        return response_text



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
