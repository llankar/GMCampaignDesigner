from __future__ import annotations

import json
from typing import Any

from modules.ai.campaign_forge.contracts import CampaignForgeRequest


def build_campaign_context(request: CampaignForgeRequest) -> dict[str, Any]:
    """Build a stable context dictionary from foundation fields."""

    foundation = request.foundation if isinstance(request.foundation, dict) else {}
    context = {
        "campaign": {
            "name": str(foundation.get("name") or "").strip(),
            "genre": str(foundation.get("genre") or "").strip(),
            "tone": str(foundation.get("tone") or "").strip(),
            "status": str(foundation.get("status") or "").strip(),
            "logline": str(foundation.get("logline") or "").strip(),
            "setting": str(foundation.get("setting") or "").strip(),
            "main_objective": str(foundation.get("main_objective") or "").strip(),
            "stakes": str(foundation.get("stakes") or "").strip(),
            "themes": [str(item).strip() for item in (foundation.get("themes") or []) if str(item).strip()],
            "notes": str(foundation.get("notes") or "").strip(),
        },
        "existing_entities": foundation.get("existing_entities") if isinstance(foundation.get("existing_entities"), dict) else {},
    }
    return context


def build_arc_refinement_prompt(context: dict[str, Any], arcs: list[dict[str, Any]]) -> str:
    """Prompt helper used when arcs are provided and need AI-assisted cleanup."""

    payload = {"context": context, "arcs": arcs}
    return (
        "Normalize these campaign arcs while preserving intent and existing links. "
        "Return strict JSON only with schema {\"arcs\": [{\"name\": str, \"summary\": str, \"objective\": str, \"thread\": str, \"status\": str, \"scenarios\": [str]}]}.\n"
        f"Input JSON:\n{json.dumps(payload, ensure_ascii=False)}"
    )
