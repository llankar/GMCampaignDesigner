from __future__ import annotations

from uuid import uuid4

from modules.ai.local_ai_client import LocalAIClient
from modules.ai.story_forge.contracts import StoryForgeRequest, StoryForgeResponse
from modules.ai.story_forge.normalizers import (
    normalize_entities,
    normalize_full_draft,
    normalize_rewrite_options,
    parse_json_strict_with_fallback,
)
from modules.ai.story_forge.prompt_builders import (
    SYSTEM_PROMPT,
    build_entity_options_prompt,
    build_full_draft_prompt,
    build_rewrite_options_prompt,
)
from modules.ai.story_forge.scene_entity_assignment import assign_unused_entities_to_scenes
from modules.core.ai import (
    AIPipelineEvent,
    EVENT_AI_PIPELINE_COMPLETED,
    EVENT_AI_PIPELINE_FAILED,
    EVENT_AI_PIPELINE_PHASE,
    EVENT_AI_PIPELINE_STARTED,
    ai_pipeline_events,
)


class StoryForgeOrchestrator:
    """Multi-step scenario generation pipeline used by Scenario Builder."""

    def __init__(self, ai_client: LocalAIClient | None = None):
        self.ai_client = ai_client or LocalAIClient()

    def run(self, request: StoryForgeRequest, request_id: str | None = None) -> StoryForgeResponse:
        ai_request_id = request_id or uuid4().hex
        self._emit_started(ai_request_id)
        try:
            self._emit_phase(ai_request_id, "context_preparation", "Preparing Story Forge context")
            rewrite_raw = self._chat(build_rewrite_options_prompt(request))
            rewrite_payload = parse_json_strict_with_fallback(rewrite_raw, fallback={"options": []})
            options = normalize_rewrite_options(rewrite_payload, brief=request.brief)
            selected_option = options[0]

            self._emit_phase(ai_request_id, "generation", "Generating entities and scenario draft")
            entities_raw = self._chat(build_entity_options_prompt(request, selected_option))
            entities_payload = parse_json_strict_with_fallback(entities_raw, fallback={"entities": {}})
            entities = normalize_entities(entities_payload)

            draft_raw = self._chat(build_full_draft_prompt(request, selected_option, entities))
            draft_payload = parse_json_strict_with_fallback(draft_raw, fallback={})

            self._emit_phase(ai_request_id, "normalization", "Normalizing Story Forge output")
            normalized_draft = normalize_full_draft(draft_payload, selected_option, entities)
            scenes_with_assignments, assignment_diagnostics = assign_unused_entities_to_scenes(
                normalized_draft["scenes"], normalized_draft["entities"], include_diagnostics=True
            )

            response = StoryForgeResponse(
                title=normalized_draft["title"],
                summary=normalized_draft["summary"],
                secrets=normalized_draft["secrets"],
                scenes=scenes_with_assignments,
                entities=normalized_draft["entities"],
                raw_steps={
                    "rewrite": rewrite_payload,
                    "entities": entities_payload,
                    "draft": draft_payload,
                    "entity_scene_assignments": assignment_diagnostics,
                },
            )
        except Exception as exc:
            self._emit_failed(ai_request_id, exc)
            raise

        self._emit_completed(ai_request_id)
        return response

    def _chat(self, prompt: str) -> str:
        return self.ai_client.chat(
            [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ]
        )

    @staticmethod
    def _emit_started(request_id: str) -> None:
        ai_pipeline_events.emit(
            AIPipelineEvent(
                event_type=EVENT_AI_PIPELINE_STARTED,
                request_id=request_id,
                phase="start",
                message="Story Forge started",
                metadata={"pipeline": "story_forge"},
            )
        )

    @staticmethod
    def _emit_phase(request_id: str, phase: str, message: str) -> None:
        ai_pipeline_events.emit(
            AIPipelineEvent(
                event_type=EVENT_AI_PIPELINE_PHASE,
                request_id=request_id,
                phase=phase,
                message=message,
                metadata={"pipeline": "story_forge"},
            )
        )

    @staticmethod
    def _emit_completed(request_id: str) -> None:
        ai_pipeline_events.emit(
            AIPipelineEvent(
                event_type=EVENT_AI_PIPELINE_COMPLETED,
                request_id=request_id,
                phase="completed",
                message="Story Forge completed",
                is_terminal=True,
                metadata={"pipeline": "story_forge"},
            )
        )

    @staticmethod
    def _emit_failed(request_id: str, exc: Exception) -> None:
        ai_pipeline_events.emit(
            AIPipelineEvent(
                event_type=EVENT_AI_PIPELINE_FAILED,
                request_id=request_id,
                phase="error",
                message=str(exc),
                is_terminal=True,
                metadata={"pipeline": "story_forge"},
            )
        )
