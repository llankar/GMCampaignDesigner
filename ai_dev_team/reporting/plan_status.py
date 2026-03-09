from __future__ import annotations

from typing import Any

try:
    from ..execution import LAST_RUN_DIRNAME
except ImportError:
    from execution import LAST_RUN_DIRNAME

_ALLOWED_STATES = {"pending", "in_progress", "completed", "failed"}


def _normalize_path_set(paths: list[str] | None) -> set[str]:
    return {p.strip() for p in (paths or []) if isinstance(p, str) and p.strip()}


def _is_last_run_artifact(path: str) -> bool:
    normalized = path.replace("\\", "/")
    return normalized.startswith(f"ai_dev_team/{LAST_RUN_DIRNAME}/")


def _is_implementation_step(description: str) -> bool:
    text = description.lower()
    return "implement" in text and "code" in text


def _is_test_step(description: str) -> bool:
    text = description.lower()
    return "pytest" in text or "run tests" in text


def _is_pr_metadata_step(description: str) -> bool:
    text = description.lower()
    return "pr metadata" in text or "branch and commit metadata" in text


def annotate_plan_states(
    *,
    plan: list[dict[str, Any]] | None,
    approved: bool,
    proposal_target_files: list[str] | None,
    changed_files: list[str] | None,
    tests: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    """Return plan entries with execution state annotations.

    Rules:
    - all steps include one of pending/in_progress/completed/failed.
    - implementation step fails when proposal target files were not changed.
    - pytest step fails when pytest return code is non-zero.
    - PR metadata step fails unless implementation and pytest both succeed.
    """
    entries = [dict(item) for item in (plan or [])]
    if not entries:
        return []

    if not approved:
        for entry in entries:
            entry["state"] = "pending"
        return entries

    target_files = _normalize_path_set(proposal_target_files)
    changed = _normalize_path_set(changed_files)
    tests_payload = tests or {}
    command = str(tests_payload.get("command") or "")
    return_code = tests_payload.get("return_code")

    implementation_ok = True
    if target_files:
        implementation_ok = bool(target_files.intersection(changed))
        if not implementation_ok and changed and all(_is_last_run_artifact(path) for path in changed):
            implementation_ok = True

    pytest_failed = False
    if "pytest" in command.lower() and return_code is not None:
        pytest_failed = int(return_code) != 0

    tests_ok = not pytest_failed

    for entry in entries:
        description = str(entry.get("description", ""))
        state = "completed"
        if _is_implementation_step(description):
            state = "completed" if implementation_ok else "failed"
        elif _is_test_step(description):
            state = "completed" if tests_ok else "failed"
        elif _is_pr_metadata_step(description):
            state = "completed" if (implementation_ok and tests_ok) else "failed"

        if state not in _ALLOWED_STATES:
            state = "failed"
        entry["state"] = state

    return entries
