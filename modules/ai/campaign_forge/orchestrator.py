from __future__ import annotations

from typing import Any

from modules.ai.campaign_forge.contracts import CampaignForgeRequest, CampaignForgeResponse
from modules.ai.campaign_forge.normalizers import coerce_arcs, coerce_foundation, coerce_generated_payload
from modules.ai.campaign_forge.prompt_builders import build_campaign_context
from modules.ai.campaign_forge.validators import (
    CampaignForgeValidationError,
    validate_arcs,
    validate_foundation,
    validate_generated_payload,
)
from modules.campaigns.services.ai.arc_generation_service import ArcGenerationService
from modules.campaigns.services.ai.arc_scenario_expansion_service import ArcScenarioExpansionService


class CampaignForgeOrchestrator:
    """Deterministic multi-stage campaign-forge orchestration pipeline."""

    def __init__(self, ai_client, scenario_wrapper=None):
        self.ai_client = ai_client
        self.scenario_wrapper = scenario_wrapper

    def run(self, request: CampaignForgeRequest) -> CampaignForgeResponse:
        # Stage 1: Build campaign context from foundation fields.
        foundation = coerce_foundation(request.foundation)
        validate_foundation(foundation)
        campaign_context = build_campaign_context(CampaignForgeRequest(foundation=foundation))

        # Stage 2: Generate arcs (or refine provided arcs).
        arcs = self._resolve_arcs(request, foundation)
        validate_arcs(arcs)

        # Stage 3: Expand scenarios per arc.
        existing_scenarios = self._resolve_existing_scenarios(request)
        expansion_service = ArcScenarioExpansionService(self.ai_client)
        generated_payload = expansion_service.generate_scenarios(
            foundation,
            arcs,
            existing_scenarios=existing_scenarios,
        )

        # Stage 4: DB-aware enrichment/validation for scenes and entity links.
        # ArcScenarioExpansionService already performs DB-aware scene/entity validation internally.
        normalized_payload = coerce_generated_payload(generated_payload)

        # Stage 5: Return a structured payload ready for persistence + preview.
        validate_generated_payload(normalized_payload, expected_arc_count=len(arcs))
        diagnostics = {
            "arc_count": len(arcs),
            "existing_scenario_count": len(existing_scenarios),
            "generated_scenario_count": sum(
                len(group.get("scenarios") or []) for group in normalized_payload.get("arcs") or []
            ),
        }

        return CampaignForgeResponse(
            campaign_context=campaign_context,
            arcs=arcs,
            generated_payload=normalized_payload,
            persistence_payload=normalized_payload,
            preview_payload=normalized_payload,
            diagnostics=diagnostics,
        )

    def _resolve_arcs(self, request: CampaignForgeRequest, foundation: dict[str, Any]) -> list[dict[str, Any]]:
        provided_arcs = coerce_arcs(request.arcs)
        if provided_arcs:
            return provided_arcs

        arc_service = ArcGenerationService(self.ai_client, self.scenario_wrapper)
        generated_arc_payload = arc_service.generate_arcs(foundation)
        arcs = coerce_arcs(generated_arc_payload.get("arcs"))
        if not arcs:
            raise CampaignForgeValidationError("Arc generation returned no usable arcs.")
        return arcs

    def _resolve_existing_scenarios(self, request: CampaignForgeRequest) -> list[dict[str, Any]]:
        if request.existing_scenarios is not None:
            return [dict(item) for item in request.existing_scenarios if isinstance(item, dict)]
        if self.scenario_wrapper is None:
            return []
        try:
            loaded = self.scenario_wrapper.load_items()
        except Exception:
            return []
        return [dict(item) for item in loaded if isinstance(item, dict)]
