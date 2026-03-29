"""Backward-compatible shim to the runtime pipeline runner."""

from modules.ai.runtime.ai_pipeline_runner import AIPipelineRunner, execute_ai_chat

__all__ = ["AIPipelineRunner", "execute_ai_chat"]
