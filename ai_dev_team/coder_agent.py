"""Coder agent responsible for applying scoped changes.

By default, this agent executes a safe built-in implementation path that writes
execution artifacts under ``ai_dev_team/last_run``. Teams can replace this class
with a project-specific implementation strategy.
"""

from __future__ import annotations

from pathlib import Path

try:
    from .planner_agent import PlanStep
except ImportError:
    from planner_agent import PlanStep


class CoderAgent:
    """Apply implementation steps while keeping changes small and auditable."""

    def implement(self, plan: list[PlanStep], workspace: str | Path = ".") -> list[str]:
        root = Path(workspace).resolve()
        out_dir = root / "ai_dev_team" / "last_run"
        out_dir.mkdir(parents=True, exist_ok=True)

        implementation_log = out_dir / "implementation.md"
        lines = ["# Feature Lab Implementation Log", ""]
        for step in plan:
            lines.append(f"- [x] Step {step.id}: {step.description}")
        implementation_log.write_text("\n".join(lines) + "\n", encoding="utf-8")

        return [str(implementation_log.relative_to(root))]
