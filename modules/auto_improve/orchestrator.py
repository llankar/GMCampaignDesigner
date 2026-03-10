from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from modules.auto_improve.command_runner import CommandExecutionError, CommandRunner
from modules.auto_improve.git_manager import GitManager
from modules.auto_improve.idea_catalog import configure_catalog, get_proposals
from modules.auto_improve.models import ExecutionReport, ImprovementProposal
from modules.auto_improve.settings import AutoImproveSettings


class AutoImproveOrchestrator:
    def __init__(self, workdir: Path | None = None):
        self.workdir = workdir or Path.cwd()
        self.settings = AutoImproveSettings.load()
        self.runner = CommandRunner()
        self.git = GitManager(self.workdir)
        configure_catalog(runner=self.runner, command_template=self.settings.agent_command, workdir=self.workdir)

    def list_proposals(self, limit: int = 5) -> list[ImprovementProposal]:
        return get_proposals(limit)

    def execute(self, proposal: ImprovementProposal) -> ExecutionReport:
        report = ExecutionReport(proposal=proposal)
        report.add_step(f"Starting auto-improvement for: {proposal.title}")

        if self.settings.dry_run:
            report.add_step("Dry-run mode is enabled: no command execution, only planning.")
            report.add_step(f"Planned agent command: {self.settings.agent_command}")
            report.success = True
            report.completed_at = datetime.now(timezone.utc)
            return report

        branch_name = f"{self.settings.branch_prefix}/{proposal.slug}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"

        try:
            self.git.create_branch(branch_name)
            report.add_step(f"Created branch: {branch_name}")

            agent_output = self.runner.run_agent(
                command_template=self.settings.agent_command,
                prompt=proposal.prompt,
                workdir=self.workdir,
            )
            report.add_step("Agent execution complete.")
            if agent_output:
                report.add_step(f"Agent output:\n{agent_output}")

            validation_output = self.runner.run_validation(
                command=self.settings.validation_command,
                workdir=self.workdir,
            )
            report.add_step("Validation command succeeded.")
            if validation_output:
                report.add_step(f"Validation output:\n{validation_output}")

            if self.settings.auto_commit:
                self.git.commit_all(f"auto-improve: {proposal.title}")
                report.add_step("Changes committed automatically.")

            report.success = True
        except (CommandExecutionError, RuntimeError) as exc:
            report.add_step(f"Execution failed: {exc}")
            report.success = False
        finally:
            report.completed_at = datetime.now(timezone.utc)

        return report
