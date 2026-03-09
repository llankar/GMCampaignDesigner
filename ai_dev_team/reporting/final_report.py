"""Final report aggregation helpers for the feature lab pipeline."""

from __future__ import annotations

from typing import Any

from .path_normalization import normalize_report_paths
from .plan_status import annotate_plan_states


def build_final_report(
    *,
    proposal: dict[str, Any],
    review: dict[str, Any],
    plan: list[dict[str, Any]] | None = None,
    changed_files: list[str] | None = None,
    tests: dict[str, Any] | None = None,
    pr: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a normalized report with non-conflicting proposal/execution fields.

    Rule enforcement:
    - Proposal quality is represented only under ``proposal_review``.
    - Execution result is represented only under ``execution`` fields.
    - If tests fail, ``execution.status`` is forced to ``failed``.
    """
    normalized_tests = tests or {"ok": False, "command": None, "return_code": None}
    normalized_changed_files = normalize_report_paths(changed_files)
    proposal_target_files = list(proposal.get("target_files", [])) if isinstance(proposal, dict) else []
    normalized_plan = annotate_plan_states(
        plan=plan,
        approved=bool(review.get("approved", False)),
        proposal_target_files=proposal_target_files,
        changed_files=normalized_changed_files,
        tests=normalized_tests,
    )

    implementation_failed = any(
        step.get("state") == "failed" and "implement" in str(step.get("description", "")).lower()
        for step in normalized_plan
    )
    pytest_failed = (
        "pytest" in str(normalized_tests.get("command") or "").lower()
        and normalized_tests.get("return_code") is not None
        and int(normalized_tests.get("return_code")) != 0
    )

    if not review.get("approved", False):
        execution_status = "not_executed"
    else:
        execution_status = "completed"
        if not normalized_tests.get("ok", False) or pytest_failed or implementation_failed:
            execution_status = "failed"

    report: dict[str, Any] = {
        "proposal": proposal,
        "proposal_review": {
            "approved": bool(review.get("approved", False)),
            "score": int(review.get("score", 0)),
            "reasons": list(review.get("reasons", [])),
        },
        "plan": normalized_plan,
        "execution": {
            "status": execution_status,
            "tests": normalized_tests,
            "changed_files": normalized_changed_files,
        },
    }

    if pr is not None:
        report["pr"] = pr

    return report
