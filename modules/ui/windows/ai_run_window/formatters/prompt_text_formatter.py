from __future__ import annotations

import json
import re

_BLOCK_RE = re.compile(r"^\[(\d+):([^\]]+)\]\s*(?:\n([\s\S]*))?$")


def format_ai_prompt_for_humans(prompt_text: str | None) -> str:
    """Format serialized AI prompt text into a human-friendly structure.

    Input is expected to follow AIPipelineRunner.serialize_prompt format:
    [1:user]\ncontent\n\n[2:system]\ncontent
    """

    payload = (prompt_text or "").strip()
    if not payload:
        return ""

    blocks = [block.strip() for block in payload.split("\n\n") if block.strip()]
    parsed_blocks: list[str] = []

    for block in blocks:
        match = _BLOCK_RE.match(block)
        if not match:
            parsed_blocks.append(block)
            continue

        index = int(match.group(1))
        role = (match.group(2) or "message").strip().upper()
        raw_content = (match.group(3) or "").strip()
        content = _format_content(raw_content)

        header = f"Message {index} — {role}"
        if content:
            parsed_blocks.append(f"{header}\n{'-' * len(header)}\n{content}")
        else:
            parsed_blocks.append(f"{header}\n{'-' * len(header)}\n(Empty message)")

    return "\n\n".join(parsed_blocks).strip()


def _format_content(content: str) -> str:
    if not content:
        return ""

    stripped = content.strip()
    if not stripped:
        return ""

    if stripped[0] in "[{":
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError:
            return stripped
        return json.dumps(parsed, indent=2, ensure_ascii=False)

    return stripped
