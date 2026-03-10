from pathlib import Path

from modules.auto_improve.catalog.idea_generation_service import IdeaGenerationService
from modules.auto_improve.command_runner import CommandRunner


class SequenceRunner(CommandRunner):
    def __init__(self, outputs: list[str]):
        self.outputs = outputs
        self.prompts: list[str] = []

    def run_agent(self, command_template: str, prompt: str, workdir: Path) -> str:
        self.prompts.append(prompt)
        return self.outputs.pop(0)


def test_generation_service_parses_json_array(tmp_path):
    runner = SequenceRunner(
        [
            '[{"slug":"npc-memory-ledger","title":"NPC Memory Ledger","summary":"Track NPC memory shifts.",'
            '"scope":"npc module","prompt":"Implement NPC memory tracking for campaigns."}]'
        ]
    )
    service = IdeaGenerationService(runner=runner, command_template="codex exec --input-file {prompt_file}", workdir=tmp_path)

    proposals = service.generate(limit=1)

    assert len(proposals) == 1
    assert proposals[0].title == "NPC Memory Ledger"


def test_generation_service_avoids_immediate_repeat_via_prompt_exclusions(tmp_path):
    runner = SequenceRunner(
        [
            '[{"slug":"faction-pressure-tracker","title":"Faction Pressure Tracker","summary":"Track tension.",'
            '"scope":"faction module","prompt":"Implement faction pressure tracking."}]',
            '[{"slug":"downtime-consequence-engine","title":"Downtime Consequence Engine","summary":"Create downtime fallout.",'
            '"scope":"downtime module","prompt":"Implement downtime fallout generation."}]',
        ]
    )
    service = IdeaGenerationService(runner=runner, command_template="codex exec --input-file {prompt_file}", workdir=tmp_path)

    first = service.generate(limit=1)
    second = service.generate(limit=1)

    assert first[0].slug != second[0].slug
    assert "Do NOT repeat excluded slugs: faction-pressure-tracker." in runner.prompts[1]


def test_generation_service_parses_json_when_logs_include_brackets(tmp_path):
    runner = SequenceRunner(
        [
            "[INFO] auto improve launch\n"
            '[{"slug":"encounter-clock","title":"Encounter Clock","summary":"Add tension clocks.",' \
            '"scope":"encounter pacing","prompt":"Implement an encounter tension clock for sessions."}]\n'
            "completed"
        ]
    )
    service = IdeaGenerationService(runner=runner, command_template="codex exec --input-file {prompt_file}", workdir=tmp_path)

    proposals = service.generate(limit=1)

    assert len(proposals) == 1
    assert proposals[0].slug == "encounter-clock"
