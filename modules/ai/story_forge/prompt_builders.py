from __future__ import annotations

import json

from modules.ai.story_forge.contracts import StoryForgeRequest


SYSTEM_PROMPT = (
    "You are Story Forge, an expert tabletop RPG scenario designer. "
    "Return valid JSON only. Avoid markdown fences and prose outside JSON."
)


def build_rewrite_options_prompt(request: StoryForgeRequest) -> str:
    context = {
        "campaign": {
            "name": request.campaign_name,
            "summary": request.campaign_summary,
        },
        "arc": {
            "name": request.arc_name,
            "summary": request.arc_summary,
            "objective": request.arc_objective,
            "thread": request.arc_thread,
        },
        "brief": request.brief,
        "existing_scenarios": request.existing_scenarios,
    }
    return (
        "Rewrite the brief into 3 distinct scenario options. "
        "Output schema: {\"options\": [{\"title\": str, \"summary\": str, \"pitch\": str}]}.\n"
        f"Context JSON:\n{json.dumps(context, ensure_ascii=False)}"
    )


def build_entity_options_prompt(request: StoryForgeRequest, selected_option: dict) -> str:
    context = {
        "selected_option": selected_option,
        "entity_catalog": request.entity_catalog,
    }
    return (
        "Propose the best fitting entities for this scenario option using the existing catalog when possible. "
        "Output schema: {\"entities\": {\"NPCs\": [str], \"Creatures\": [str], \"Bases\": [str], \"Places\": [str], \"Maps\": [str], \"Factions\": [str], \"Objects\": [str]}}.\n"
        f"Context JSON:\n{json.dumps(context, ensure_ascii=False)}"
    )


def build_full_draft_prompt(request: StoryForgeRequest, selected_option: dict, entities: dict) -> str:
    context = {
        "selected_option": selected_option,
        "entities": entities,
        "campaign": {
            "name": request.campaign_name,
            "summary": request.campaign_summary,
        },
        "arc": {
            "name": request.arc_name,
            "summary": request.arc_summary,
            "objective": request.arc_objective,
            "thread": request.arc_thread,
        },
    }
    return (
        "Write the full scenario draft. "
        "Output schema: {\"title\": str, \"summary\": str, \"secrets\": str, "
        "\"scenes\": [{\"Title\": str, \"Summary\": str, \"SceneType\": str}], "
        "\"entities\": {\"NPCs\": [str], \"Creatures\": [str], \"Bases\": [str], \"Places\": [str], \"Maps\": [str], \"Factions\": [str], \"Objects\": [str]}}.\n"
        f"Context JSON:\n{json.dumps(context, ensure_ascii=False)}"
    )
