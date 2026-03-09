"""Planner agent translating a proposal into executable steps."""

from __future__ import annotations

from dataclasses import dataclass

try:
    from .feature_agent import FeatureProposal
except ImportError:
    from feature_agent import FeatureProposal


@dataclass
class PlanStep:
    id: int
    description: str


class PlannerAgent:
    """Create an implementation plan with explicit sequencing."""

    def plan(self, proposal: FeatureProposal) -> list[PlanStep]:
        steps = [
            "Inspect target files and current architecture constraints.",
            "Implement minimal code changes required for the proposal.",
            "Add or update pytest coverage for the new behavior.",
            "Run pytest and collect output.",
            "Prepare branch and commit metadata for PR automation.",
        ]
        return [PlanStep(id=i + 1, description=s) for i, s in enumerate(steps)]
