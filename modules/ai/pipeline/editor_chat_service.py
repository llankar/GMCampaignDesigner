"""Utilities for pipeline editor chat service."""

from __future__ import annotations

from modules.ai.runtime import AIPipelineRunner


def run_ai_editor_chat(
    ai_client,
    messages,
    *,
    pipeline_name: str,
    feature: str,
    entity_type: str,
    action_label: str,
    request_id: str | None = None,
    phase: str = "llm_call",
    phase_message: str | None = None,
    **chat_kwargs,
):
    """Run editor AI chat requests through a single pipeline-aware service."""

    runner = AIPipelineRunner(ai_client=ai_client, pipeline_name=pipeline_name, request_id=request_id)
    return runner.run_chat(
        messages,
        phase=phase,
        phase_message=phase_message or action_label,
        context_metadata={
            "feature": feature,
            "entity_type": entity_type,
            "action_label": action_label,
        },
        **chat_kwargs,
    )
