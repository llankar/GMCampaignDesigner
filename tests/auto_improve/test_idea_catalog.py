"""Regression tests for idea catalog."""

from pathlib import Path

from modules.auto_improve.command_runner import CommandRunner
from modules.auto_improve.idea_catalog import configure_catalog, get_proposals


class StubRunner(CommandRunner):
    def __init__(self):
        """Initialize the StubRunner instance."""
        self.prompts: list[str] = []

    def run_agent(self, command_template: str, prompt: str, workdir: Path) -> str:
        """Run agent."""
        self.prompts.append(prompt)
        return (
            '[{"slug":"gm-scene-framing","title":"GM Scene Framing Helper","summary":"Suggest scene openings.",'
            '"scope":"scenario module","prompt":"Implement scene framing support for campaigns."}]'
        )


def test_get_proposals_returns_generated_content(tmp_path):
    """Verify that get proposals returns generated content."""
    runner = StubRunner()
    configure_catalog(runner=runner, command_template="codex exec --input-file {prompt_file}", workdir=tmp_path)

    proposals = get_proposals(limit=1)

    assert len(proposals) == 1
    assert proposals[0].slug == "gm-scene-framing"
    assert runner.prompts
