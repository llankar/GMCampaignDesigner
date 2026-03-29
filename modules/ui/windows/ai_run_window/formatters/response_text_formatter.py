from __future__ import annotations

import json
import re

_JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*\n([\s\S]*?)\n```", re.IGNORECASE)


def format_ai_response_for_humans(response_text: str | None) -> str:
    """Format AI response text for easier reading.

    - Pretty-print full JSON payloads.
    - Pretty-print fenced JSON blocks while preserving surrounding text.
    - Return original text when no JSON is detected.
    """

    payload = (response_text or "").strip()
    if not payload:
        return ""

    pretty_payload = _pretty_print_if_json(payload)
    if pretty_payload is not None:
        return pretty_payload

    return _pretty_print_json_code_blocks(payload)


def _pretty_print_if_json(text: str) -> str | None:
    if not text or text[0] not in "[{":
        return None

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return None

    return json.dumps(parsed, indent=2, ensure_ascii=False)


def _pretty_print_json_code_blocks(text: str) -> str:
    def _replace(match: re.Match[str]) -> str:
        raw_block = match.group(1).strip()
        pretty = _pretty_print_if_json(raw_block)
        if pretty is None:
            return match.group(0)
        return f"```json\n{pretty}\n```"

    return _JSON_BLOCK_RE.sub(_replace, text)
