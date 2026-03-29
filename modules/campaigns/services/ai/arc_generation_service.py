from __future__ import annotations

from typing import Any

from modules.campaigns.services.ai.json_parsing import (
    normalize_arc_generation_payload,
    parse_json_relaxed,
)
from modules.campaigns.services.ai.prompt_builders import build_arc_generation_prompt
from modules.campaigns.shared.arc_status import canonicalize_arc_status
from modules.ai.runtime import AIPipelineRunner


class ArcGenerationService:
    """Generate campaign arcs from scenario summaries using a strict-JSON AI contract."""

    def __init__(self, ai_client, scenario_wrapper):
        self.ai_client = ai_client
        self.scenario_wrapper = scenario_wrapper

    def load_scenario_catalog(self) -> list[dict[str, Any]]:
        scenarios = self.scenario_wrapper.load_items() if self.scenario_wrapper else []
        return [dict(item) for item in (scenarios or []) if isinstance(item, dict)]

    def generate_arcs(self, foundation: dict[str, Any]) -> dict[str, Any]:
        scenarios = self.load_scenario_catalog()
        prompt = build_arc_generation_prompt(foundation=foundation, scenarios=scenarios)
        available_titles = self._build_available_scenario_aliases(scenarios)

        messages = [
            {
                "role": "system",
                "content": "Plan RPG campaign arcs and return strict JSON only.",
            },
            {"role": "user", "content": prompt},
        ]

        runner = AIPipelineRunner(self.ai_client, pipeline_name="campaign.arc_generation")
        last_error: Exception | None = None
        for attempt in range(2):
            raw_response = runner.run_chat(
                messages,
                phase="arc_generation",
                phase_message=f"Generating campaign arcs (attempt {attempt + 1}/2)",
                context_metadata={
                    "feature": "campaign_builder",
                    "action_label": "Generate campaign arcs",
                },
            )
            try:
                parsed = parse_json_relaxed(raw_response)
                normalized = normalize_arc_generation_payload(parsed, available_scenarios=available_titles)
                normalized["arcs"] = [self._normalize_arc(arc) for arc in normalized["arcs"]]
                return normalized
            except Exception as exc:
                last_error = exc
                if attempt == 1:
                    raise
                messages = [
                    *messages,
                    {"role": "assistant", "content": str(raw_response)},
                    {
                        "role": "user",
                        "content": (
                            "Your previous JSON did not satisfy the campaign-arc constraints. "
                            f"Fix it and return strict JSON only. Error: {exc}. "
                            "Ensure every arc uses exact existing scenario titles and that each arc groups connected scenarios into a coherent progression instead of isolated single-scenario arcs."
                        ),
                    },
                ]

        raise RuntimeError(f"Arc generation failed: {last_error}")

    def _normalize_arc(self, arc: dict[str, Any]) -> dict[str, Any]:
        return {
            "name": (arc.get("name") or "").strip(),
            "summary": (arc.get("summary") or "").strip(),
            "objective": (arc.get("objective") or "").strip(),
            "status": canonicalize_arc_status(arc.get("status")),
            "thread": (arc.get("thread") or "").strip(),
            "scenarios": [str(title).strip() for title in (arc.get("scenarios") or []) if str(title).strip()],
        }

    @staticmethod
    def _build_available_scenario_aliases(scenarios: list[dict[str, Any]]) -> dict[str, str]:
        aliases: dict[str, str] = {}
        for item in scenarios:
            title = str(item.get("Title") or item.get("Name") or "").strip()
            if not title:
                continue

            aliases[title] = title

            summary = str(item.get("Summary") or item.get("Description") or item.get("Logline") or "").strip()
            if summary:
                aliases[f"{title}: {summary}"] = title

        return aliases
