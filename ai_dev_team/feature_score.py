"""Scoring guardrails for feature proposals."""

from __future__ import annotations

from dataclasses import dataclass

try:
    from .feature_agent import FeatureProposal
except ImportError:
    from feature_agent import FeatureProposal


@dataclass
class FeatureScoreResult:
    approved: bool
    score: int
    reasons: list[str]


class FeatureScorer:
    """Reject risky or low-value features with transparent rules."""

    RISKY_KEYWORDS = {"rewrite", "migration", "delete", "remove module", "database drop"}

    def evaluate(self, proposal: FeatureProposal) -> FeatureScoreResult:
        reasons: list[str] = []
        score = 50

        title = proposal.title.lower()
        rationale = proposal.rationale.lower()
        combined = f"{title} {rationale}"

        if any(k in combined for k in self.RISKY_KEYWORDS):
            reasons.append("Rejected because proposal appears risky or destructive.")
            score -= 60

        if "usability" in rationale or "automation" in rationale or "ui" in rationale:
            score += 20
        else:
            reasons.append("Proposal is not clearly tied to usability/automation/UI.")

        if len(proposal.target_files) <= 6:
            score += 10
        else:
            reasons.append("Target file scope is too wide.")
            score -= 20

        if len(proposal.acceptance_criteria) >= 3:
            score += 10

        approved = score >= 60
        if approved and not reasons:
            reasons.append("Approved: scoped, useful, and low-risk.")
        return FeatureScoreResult(approved=approved, score=score, reasons=reasons)
