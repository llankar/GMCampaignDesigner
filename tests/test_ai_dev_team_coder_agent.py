from ai_dev_team.coder_agent import CoderAgent
from ai_dev_team.planner_agent import PlanStep


def test_coder_agent_generates_architecture_snapshot_artifact(tmp_path):
    changed = CoderAgent().implement(
        [
            PlanStep(id=1, description="Implement minimal code changes required for the proposal."),
            PlanStep(id=2, description="Run pytest and collect output."),
        ],
        workspace=tmp_path,
    )

    assert "docs/architecture/ai_dev_team_summary.md" in changed
    assert (tmp_path / "docs" / "architecture" / "ai_dev_team_summary.md").exists()
    assert (tmp_path / "ai_dev_team" / "last_run" / "implementation.md").exists()
