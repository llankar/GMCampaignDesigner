from __future__ import annotations


def build_idea_prompt(limit: int, excluded_slugs: set[str]) -> str:
    excluded = ", ".join(sorted(excluded_slugs)) if excluded_slugs else "none"
    return (
        "You are reviewing the current GMCampaignDesigner repository.\n"
        "Propose NEW product features for tabletop RPG Game Masters only.\n"
        "Hard constraints:\n"
        "- Output must be strictly in English.\n"
        "- Ideas must be RPG/GM oriented (story prep, campaign play, NPCs, encounters, factions, clues, etc.).\n"
        "- Do NOT propose coding/tooling/devops/refactor features.\n"
        "- Do NOT repeat excluded slugs: "
        f"{excluded}.\n"
        f"Generate exactly {limit} proposals as JSON array only (no markdown, no prose).\n"
        "Schema per item:\n"
        "{\"slug\": string, \"title\": string, \"summary\": string, \"scope\": string, \"prompt\": string}\n"
        "Slug must be lowercase kebab-case and unique in this response.\n"
        "The prompt field must be a concrete implementation request for Codex CLI.\n"
    )
