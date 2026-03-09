"""Final report aggregation helpers for the feature lab pipeline."""

from __future__ import annotations

from typing import Any


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
    normalized_changed_files = changed_files or []

    if not review.get("approved", False):
        execution_status = "not_executed"
    else:
        execution_status = "completed"
        if not normalized_tests.get("ok", False):
            execution_status = "failed"

    report: dict[str, Any] = {
        "proposal": proposal,
        "proposal_review": {
            "approved": bool(review.get("approved", False)),
            "score": int(review.get("score", 0)),
            "reasons": list(review.get("reasons", [])),
        },
        "plan": plan or [],
        "execution": {
            "status": execution_status,
            "tests": normalized_tests,
            "changed_files": normalized_changed_files,
        },
    }

    if pr is not None:
        report["pr"] = pr

    return report
