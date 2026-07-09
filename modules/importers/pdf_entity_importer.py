"""Import helpers for importers PDF entity."""

import json

from modules.helpers.text_helpers import ai_text_to_rtf_json
from modules.helpers.logging_helper import log_function, log_module_import

log_module_import(__name__)


@log_function
def parse_json_relaxed(payload: str):
    """Parse JSON from a possibly noisy AI response."""
    if not payload:
        raise RuntimeError("Empty AI response")
    text = payload.strip()
    if text.startswith("```"):
        # Strip optional markdown fences
        import re as _re

        text = _re.sub(r"^```(json)?", "", text, flags=_re.IGNORECASE).strip()
        text = text.rstrip("`").strip()
    try:
        return json.loads(text)
    except Exception:
        pass
    start = None
    for idx, ch in enumerate(text):
        if ch in "[{":
            start = idx
            break
    if start is None:
        raise RuntimeError("Failed to locate JSON in response")
    snippet = text[start:]
    for end in range(len(snippet), max(len(snippet) - 2000, 0), -1):
        try:
            return json.loads(snippet[:end])
        except Exception:
            continue
    raise RuntimeError("Failed to parse JSON from AI response")


def format_longtext_value(value):
    """Return a human-readable plain-text value for longtext fields.

    AI importers may return longtext fields as lists. Store those lists as
    readable text instead of JSON so editor fields display naturally.
    """
    if isinstance(value, dict) and "text" in value:
        return value
    if value is None:
        return ""
    if isinstance(value, list):
        return _format_longtext_list(value)
    if isinstance(value, dict):
        return _format_longtext_dict(value)
    return str(value)


def _format_longtext_list(items, *, indent: int = 0) -> str:
    """Format list items as newline bullets, including nested dictionaries."""
    lines: list[str] = []
    prefix = " " * indent
    for item in items:
        if item is None:
            continue
        if isinstance(item, dict):
            body = _format_longtext_dict(item, indent=indent + 2)
            if body.strip():
                lines.append(f"{prefix}- {body.lstrip()}")
            continue
        if isinstance(item, list):
            body = _format_longtext_list(item, indent=indent + 2)
            if body.strip():
                lines.append(f"{prefix}- {body.lstrip()}")
            continue
        text = str(item).strip()
        if text:
            lines.append(f"{prefix}- {text}")
    return "\n".join(lines)


def _format_longtext_dict(data, *, indent: int = 0) -> str:
    """Format dictionaries as readable key/value text instead of raw JSON."""
    lines: list[str] = []
    prefix = " " * indent
    for key, value in data.items():
        if value is None:
            continue
        label = str(key).strip()
        if not label:
            continue
        if isinstance(value, dict):
            nested = _format_longtext_dict(value, indent=indent + 2)
            if nested.strip():
                lines.append(f"{prefix}{label}:")
                lines.append(nested)
            continue
        if isinstance(value, list):
            nested = _format_longtext_list(value, indent=indent + 2)
            if nested.strip():
                lines.append(f"{prefix}{label}:")
                lines.append(nested)
            continue
        text = str(value).strip()
        if text:
            lines.append(f"{prefix}{label}: {text}")
    return "\n".join(lines)


def to_longtext(value):
    """Convert plain strings into the rich-text JSON structure used by the DB."""
    formatted = format_longtext_value(value)
    if isinstance(formatted, dict) and "text" in formatted:
        return formatted
    return ai_text_to_rtf_json(str(formatted) if formatted is not None else "")


def to_list(value) -> list[str]:
    """Normalize common list-shaped values into a list of strings."""
    if value is None:
        return []
    if isinstance(value, list):
        return [
            str(item).strip()
            for item in value
            if item is not None and str(item).strip()
        ]
    if isinstance(value, dict):
        return [
            str(item).strip()
            for item in value.values()
            if item is not None and str(item).strip()
        ]
    if isinstance(value, str):
        # Handle the branch where isinstance(value, str).
        parts = []
        for line in value.splitlines():
            for part in line.split(","):
                # Process each part from line.split(',').
                cleaned = part.strip()
                if cleaned:
                    parts.append(cleaned)
        return parts
    cleaned = str(value).strip()
    return [cleaned] if cleaned else []
