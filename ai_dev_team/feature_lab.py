from __future__ import annotations

import argparse
import json
from pathlib import Path

try:
    from .coder_agent import CoderAgent
    from .context_builder import ContextBuilder
    from .feature_agent import FeatureAgent
    from .feature_score import FeatureScorer
    from .planner_agent import PlannerAgent
    from .pr_agent import PRAgent
    from .repo_analyzer import analyze_repository, architecture_summary_text
    from .test_agent import TestAgent
except ImportError:
    from coder_agent import CoderAgent
    from context_builder import ContextBuilder
    from feature_agent import FeatureAgent
    from feature_score import FeatureScorer
    from planner_agent import PlannerAgent
    from pr_agent import PRAgent
    from repo_analyzer import analyze_repository, architecture_summary_text
    from test_agent import TestAgent


def run_architecture_summary_command(workspace: str | Path = ".") -> str:
    """Return architecture summary text for the requested workspace."""
    return architecture_summary_text(workspace)


def run_feature_lab(workspace: str | Path = ".", commit: bool = False, push: bool = False) -> dict:
    root = Path(workspace).resolve()
    summary = analyze_repository(root)
    context = ContextBuilder().build(summary)
    proposal = FeatureAgent().propose(context)
    score = FeatureScorer().evaluate(proposal)
    if not score.approved:
        return {"status": "rejected", "score": score.score, "reasons": score.reasons}

    plan = PlannerAgent().plan(proposal)
    changed_files = CoderAgent().implement(plan, root)
    tests = TestAgent().run(root)
    result: dict = {
        "status": "completed" if tests.ok else "test_failed",
        "proposal": proposal.__dict__,
        "score": {"value": score.score, "reasons": score.reasons},
        "plan": [step.__dict__ for step in plan],
        "changed_files": changed_files,
        "tests": {"ok": tests.ok, "command": tests.command, "return_code": tests.return_code},
    }
    if commit:
        msg = f"feat: {proposal.title.lower()}"
        result["pr"] = PRAgent().create_branch_and_commit(root, msg, push=push).__dict__
    return result


def main() -> None:
    p = argparse.ArgumentParser(description="Run autonomous feature lab pipeline.")
    p.add_argument("--workspace", default=".", help="Repository root path")
    p.add_argument(
        "--architecture-summary",
        action="store_true",
        help="Print a quick repository architecture summary and exit",
    )
    p.add_argument("--commit", action="store_true", help="Create git branch and commit")
    p.add_argument("--push", action="store_true", help="Push branch to origin (implies --commit)")
    a = p.parse_args()
    if a.architecture_summary:
        print(run_architecture_summary_command(a.workspace))
        return
    print(json.dumps(run_feature_lab(a.workspace, commit=(a.commit or a.push), push=a.push), indent=2))


if __name__ == "__main__":
    main()
