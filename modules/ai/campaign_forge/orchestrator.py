"""Orchestration helpers for campaign forge."""
from __future__ import annotations

import time
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
from modules.helpers.logging_helper import log_error, log_info, log_warning


class CampaignForgeOrchestrator:
    """Deterministic multi-stage campaign-forge orchestration pipeline."""

    def __init__(self, ai_client, scenario_wrapper=None):
        """Initialize the CampaignForgeOrchestrator instance."""
        self.ai_client = ai_client
        self.scenario_wrapper = scenario_wrapper

    def run(self, request: CampaignForgeRequest) -> CampaignForgeResponse:
        """Run the operation."""
        total_started = time.perf_counter()
        self._log_event(
            "campaign_forge.pipeline.start",
            "pipeline_started",
            arc_count_requested=len(coerce_arcs(request.arcs)),
            existing_scenario_count_requested=len(request.existing_scenarios or []),
        )

        try:
            # Stage 1: Build campaign context from foundation fields.
            stage_started = self._log_stage_start("foundation", "foundation_started")
            foundation = coerce_foundation(request.foundation)
            validate_foundation(foundation)
            campaign_context = build_campaign_context(CampaignForgeRequest(foundation=foundation))
            self._log_stage_end(
                "foundation",
                "foundation_completed",
                stage_started,
                campaign_name=str(foundation.get("name") or "").strip(),
            )

            # Stage 2: Generate arcs (or refine provided arcs).
            stage_started = self._log_stage_start("arcs", "arcs_started")
            arcs = self._resolve_arcs(request, foundation)
            validate_arcs(arcs)
            self._log_stage_end("arcs", "arcs_completed", stage_started, arc_count=len(arcs))

            # Stage 3: Expand scenarios per arc.
            stage_started = self._log_stage_start("scenario_generation", "scenario_generation_started")
            existing_scenarios = self._resolve_existing_scenarios(request)
            expansion_service = ArcScenarioExpansionService(self.ai_client)
            generated_payload = expansion_service.generate_scenarios(
                foundation,
                arcs,
                existing_scenarios=existing_scenarios,
            )
            self._log_stage_end(
                "scenario_generation",
                "scenario_generation_completed",
                stage_started,
                existing_scenario_count=len(existing_scenarios),
            )

            # Stage 4: DB-aware enrichment/validation for scenes and entity links.
            # ArcScenarioExpansionService already performs DB-aware scene/entity validation internally.
            stage_started = self._log_stage_start("payload_normalization", "payload_normalization_started")
            normalized_payload = coerce_generated_payload(generated_payload)

            # Stage 5: Return a structured payload ready for persistence + preview.
            validate_generated_payload(normalized_payload, expected_arc_count=len(arcs))
            counts = self._collect_generated_counts(normalized_payload)
            self._log_stage_end(
                "payload_normalization",
                "payload_normalization_completed",
                stage_started,
                generated_arc_count=counts["arc_count"],
                generated_scenario_count=counts["scenario_count"],
                generated_scene_count=counts["scene_count"],
            )
        except CampaignForgeValidationError as exc:
            self._log_event(
                "campaign_forge.pipeline.validation_error",
                "pipeline_validation_error",
                level="error",
                error_type=type(exc).__name__,
                error=str(exc),
                elapsed_ms=self._elapsed_ms(total_started),
            )
            raise
        except Exception as exc:
            self._log_event(
                "campaign_forge.pipeline.error",
                "pipeline_failed",
                level="error",
                error_type=type(exc).__name__,
                error=str(exc),
                elapsed_ms=self._elapsed_ms(total_started),
            )
            raise

        diagnostics = {
            "arc_count": len(arcs),
            "existing_scenario_count": len(existing_scenarios),
            "generated_scenario_count": sum(
                len(group.get("scenarios") or []) for group in normalized_payload.get("arcs") or []
            ),
            "generated_scene_count": self._collect_generated_counts(normalized_payload)["scene_count"],
            "elapsed_ms": self._elapsed_ms(total_started),
        }

        self._log_event(
            "campaign_forge.pipeline.completed",
            "pipeline_completed",
            arc_count=diagnostics["arc_count"],
            existing_scenario_count=diagnostics["existing_scenario_count"],
            generated_scenario_count=diagnostics["generated_scenario_count"],
            generated_scene_count=diagnostics["generated_scene_count"],
            elapsed_ms=diagnostics["elapsed_ms"],
        )

        return CampaignForgeResponse(
            campaign_context=campaign_context,
            arcs=arcs,
            generated_payload=normalized_payload,
            persistence_payload=normalized_payload,
            preview_payload=normalized_payload,
            diagnostics=diagnostics,
        )

    def _resolve_arcs(self, request: CampaignForgeRequest, foundation: dict[str, Any]) -> list[dict[str, Any]]:
        """Resolve arcs."""
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
        """Resolve existing scenarios."""
        if request.existing_scenarios is not None:
            return [dict(item) for item in request.existing_scenarios if isinstance(item, dict)]
        if self.scenario_wrapper is None:
            self._log_event(
                "campaign_forge.stage.warning",
                "existing_scenarios_unavailable",
                level="warning",
                detail="Scenario wrapper missing; continuing with empty existing_scenarios.",
            )
            return []
        try:
            # Keep existing scenarios resilient if this step fails.
            loaded = self.scenario_wrapper.load_items()
        except Exception as exc:
            self._log_event(
                "campaign_forge.stage.warning",
                "existing_scenarios_load_failed",
                level="warning",
                detail=str(exc),
                error_type=type(exc).__name__,
            )
            return []
        return [dict(item) for item in loaded if isinstance(item, dict)]

    def _log_stage_start(self, stage: str, action: str) -> float:
        """Internal helper for log stage start."""
        started_at = time.perf_counter()
        self._log_event("campaign_forge.stage.start", action, stage=stage)
        return started_at

    def _log_stage_end(self, stage: str, action: str, started_at: float, **details: Any) -> None:
        """Internal helper for log stage end."""
        self._log_event(
            "campaign_forge.stage.end",
            action,
            stage=stage,
            elapsed_ms=self._elapsed_ms(started_at),
            **details,
        )

    def _log_event(self, event: str, action: str, *, level: str = "info", **details: Any) -> None:
        """Internal helper for log event."""
        detail_parts = [f"{key}={details[key]!r}" for key in sorted(details.keys())]
        message = f"event={event} action={action}"
        if detail_parts:
            message = f"{message} {' '.join(detail_parts)}"

        if level == "error":
            log_error(message, func_name="campaign_forge.orchestrator")
            return
        if level == "warning":
            log_warning(message, func_name="campaign_forge.orchestrator")
            return
        log_info(message, func_name="campaign_forge.orchestrator")

    @staticmethod
    def _elapsed_ms(started_at: float) -> int:
        """Internal helper for elapsed ms."""
        return max(0, int((time.perf_counter() - started_at) * 1000))

    @staticmethod
    def _collect_generated_counts(payload: dict[str, Any]) -> dict[str, int]:
        """Collect generated counts."""
        arc_groups = [item for item in (payload.get("arcs") or []) if isinstance(item, dict)]
        scenario_count = 0
        scene_count = 0
        for group in arc_groups:
            # Process each group from arc_groups.
            scenarios = [item for item in (group.get("scenarios") or []) if isinstance(item, dict)]
            scenario_count += len(scenarios)
            for scenario in scenarios:
                # Process each scenario from scenarios.
                scenes = scenario.get("scene_ideas") or scenario.get("scenes") or []
                if isinstance(scenes, list):
                    scene_count += len([scene for scene in scenes if isinstance(scene, dict)])
        return {
            "arc_count": len(arc_groups),
            "scenario_count": scenario_count,
            "scene_count": scene_count,
        }
