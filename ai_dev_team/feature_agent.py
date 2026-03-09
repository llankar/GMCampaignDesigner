"""Feature proposal agent.

This default implementation is deterministic and avoids LLM/network dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class FeatureProposal:
    title: str
    rationale: str
    target_files: list[str]
    acceptance_criteria: list[str]


class FeatureAgent:
    """Generate one useful feature proposal from repository context."""

    def propose(self, context: str) -> FeatureProposal:
        has_tests = "Tests:" in context and not context.endswith("Tests: 0")
        criteria = [
            "Add a small command-line utility that summarizes repository architecture.",
            "Do not modify existing business modules.",
            "Add at least one focused pytest validating the new utility.",
        ]
        if has_tests:
            criteria.append("New test passes in the current pytest suite.")

        return FeatureProposal(
            title="Add AI Dev Team architecture summary command",
            rationale=(
                "A lightweight automation entry point improves developer usability by producing "
                "a quick architecture snapshot before autonomous feature generation."
            ),
            target_files=[
                "ai_dev_team/feature_lab.py",
                "ai_dev_team/repo_analyzer.py",
                "tests/test_ai_dev_team_repo_analyzer.py",
            ],
            acceptance_criteria=criteria,
        )
