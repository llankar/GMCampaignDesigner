from __future__ import annotations

import json
from pathlib import Path
from json import JSONDecodeError

from modules.auto_improve.command_runner import CommandRunner
from modules.auto_improve.models import ImprovementProposal

from modules.auto_improve.catalog.prompt_builder import build_idea_prompt


class IdeaGenerationService:
    def __init__(self, runner: CommandRunner, command_template: str, workdir: Path):
        self._runner = runner
        self._command_template = command_template
        self._workdir = workdir
        self._last_slugs: set[str] = set()

    def generate(self, limit: int = 10) -> list[ImprovementProposal]:
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
        if not text:
            raise ValueError("Idea generator output is empty.")

        candidates = [text]
        candidates.extend(IdeaGenerationService._extract_fenced_blocks(text))

        for candidate in candidates:
            payload = IdeaGenerationService._decode_first_json_array(candidate)
            if payload is not None:
                return payload

        raise ValueError("No valid JSON array found in idea generator output.")

    @staticmethod
    def _extract_fenced_blocks(text: str) -> list[str]:
        blocks: list[str] = []
        current: list[str] | None = None

        for line in text.splitlines():
            if line.strip().startswith("```"):
                if current is None:
                    current = []
                else:
                    block = "\n".join(current).strip()
                    if block:
                        blocks.append(block)
                    current = None
                continue
            if current is not None:
                current.append(line)

        if current:
            block = "\n".join(current).strip()
            if block:
                blocks.append(block)

        return blocks

    @staticmethod
    def _decode_first_json_array(text: str):
        stripped = text.strip()
        if not stripped:
            return None

        try:
            payload = json.loads(stripped)
            if isinstance(payload, list):
                return payload
        except JSONDecodeError:
            pass

        decoder = json.JSONDecoder()
        for index, char in enumerate(stripped):
            if char != "[":
                continue
            try:
                payload, _ = decoder.raw_decode(stripped[index:])
            except JSONDecodeError:
                continue
            if isinstance(payload, list):
                return payload

        return None
