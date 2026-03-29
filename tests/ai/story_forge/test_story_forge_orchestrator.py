from modules.ai.story_forge.contracts import StoryForgeRequest
from modules.ai.story_forge.orchestrator import StoryForgeOrchestrator
from modules.core.ai import (
    EVENT_AI_PIPELINE_COMPLETED,
    EVENT_AI_PIPELINE_FAILED,
    EVENT_AI_PIPELINE_PHASE,
    EVENT_AI_PIPELINE_STARTED,
    ai_pipeline_events,
)


class _FakeAIClient:
    def __init__(self, responses):
        self._responses = list(responses)

    def chat(self, _messages):
        return self._responses.pop(0)



def _request() -> StoryForgeRequest:
    return StoryForgeRequest(brief="A broken city and a silent witness")



def test_story_forge_orchestrator_emits_pipeline_events(monkeypatch):
    from modules.ai.story_forge import orchestrator as orchestrator_module

    monkeypatch.setattr(orchestrator_module, "build_rewrite_options_prompt", lambda _r: "rewrite")
    monkeypatch.setattr(orchestrator_module, "build_entity_options_prompt", lambda _r, _o: "entities")
    monkeypatch.setattr(orchestrator_module, "build_full_draft_prompt", lambda _r, _o, _e: "draft")
    monkeypatch.setattr(orchestrator_module, "parse_json_strict_with_fallback", lambda raw, fallback: raw)
    monkeypatch.setattr(orchestrator_module, "normalize_rewrite_options", lambda _payload, brief: [brief])
    monkeypatch.setattr(orchestrator_module, "normalize_entities", lambda _payload: {"NPCs": ["Eloi"]})
    monkeypatch.setattr(
        orchestrator_module,
        "normalize_full_draft",
        lambda _payload, _selected, entities: {
            "title": "Draft",
            "summary": "Summary",
            "secrets": "Secret",
            "scenes": [{"Title": "Scene 1"}],
            "entities": entities,
        },
    )
    monkeypatch.setattr(
        orchestrator_module,
        "assign_unused_entities_to_scenes",
        lambda scenes, entities, include_diagnostics: (scenes, {"unassigned": []}),
    )

    events = []
    unsubscribe = ai_pipeline_events.subscribe("*", events.append)
    try:
        orchestrator = StoryForgeOrchestrator(ai_client=_FakeAIClient([{"options": []}, {"entities": {}}, {}]))
        response = orchestrator.run(_request(), request_id="req-story-forge-1")
    finally:
        unsubscribe()

    assert response.title == "Draft"
    assert [event.event_type for event in events] == [
        EVENT_AI_PIPELINE_STARTED,
        EVENT_AI_PIPELINE_PHASE,
        EVENT_AI_PIPELINE_PHASE,
        EVENT_AI_PIPELINE_PHASE,
        EVENT_AI_PIPELINE_COMPLETED,
    ]
    assert [event.phase for event in events[1:4]] == [
        "context_preparation",
        "generation",
        "normalization",
    ]
    assert all(event.request_id == "req-story-forge-1" for event in events)



def test_story_forge_orchestrator_emits_failed_event_on_error(monkeypatch):
    from modules.ai.story_forge import orchestrator as orchestrator_module

    monkeypatch.setattr(orchestrator_module, "build_rewrite_options_prompt", lambda _r: "rewrite")

    events = []
    unsubscribe = ai_pipeline_events.subscribe("*", events.append)
    try:
        orchestrator = StoryForgeOrchestrator(ai_client=_FakeAIClient([]))
        try:
            orchestrator.run(_request(), request_id="req-story-forge-fail")
        except IndexError:
            pass
    finally:
        unsubscribe()

    assert events[0].event_type == EVENT_AI_PIPELINE_STARTED
    assert events[-1].event_type == EVENT_AI_PIPELINE_FAILED
    assert events[-1].request_id == "req-story-forge-fail"
