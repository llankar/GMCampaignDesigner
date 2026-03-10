from __future__ import annotations

import json
from pathlib import Path

from modules.auto_improve.command_runner import CommandRunner
from modules.auto_improve.models import ImprovementProposal

from modules.auto_improve.catalog.prompt_builder import build_idea_prompt


class IdeaGenerationService:
    def __init__(self, runner: CommandRunner, command_template: str, workdir: Path):
        self._runner = runner
        self._command_template = command_template
        self._workdir = workdir
        self._last_slugs: set[str] = set()

    def generate(self, limit: int = 5) -> list[ImprovementProposal]:
        normalized_limit = max(1, limit)
        prompt = build_idea_prompt(normalized_limit, self._last_slugs)
        raw_output = self._runner.run_agent(
            command_template=self._command_template,
            prompt=prompt,
            workdir=self._workdir,
        )
        proposals = self._parse(raw_output, normalized_limit)
        self._last_slugs = {proposal.slug for proposal in proposals}
        return proposals

    def _parse(self, raw_output: str, limit: int) -> list[ImprovementProposal]:
        payload = self._extract_json(raw_output)
        if not isinstance(payload, list):
            raise ValueError("Idea generator output must be a JSON array.")

        proposals: list[ImprovementProposal] = []
        seen_slugs: set[str] = set()
        for item in payload[:limit]:
            if not isinstance(item, dict):
                continue
            slug = str(item.get("slug", "")).strip().lower()
            title = str(item.get("title", "")).strip()
            summary = str(item.get("summary", "")).strip()
            scope = str(item.get("scope", "")).strip()
            prompt = str(item.get("prompt", "")).strip()
            if not (slug and title and summary and scope and prompt):
                continue
            if slug in seen_slugs:
                continue
            seen_slugs.add(slug)
            proposals.append(
                ImprovementProposal(
                    slug=slug,
                    title=title,
                    summary=summary,
                    scope=scope,
                    prompt=prompt,
                )
            )

        if not proposals:
            raise ValueError("Idea generator did not return any valid proposal.")
        return proposals

    @staticmethod
    def _extract_json(raw_output: str):
        text = raw_output.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            text = "\n".join(lines).strip()

        start = text.find("[")
        end = text.rfind("]")
        if start == -1 or end == -1 or end < start:
            raise ValueError("No JSON array found in idea generator output.")

        return json.loads(text[start : end + 1])
