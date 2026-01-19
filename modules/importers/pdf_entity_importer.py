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


def to_longtext(value):
    """Convert plain strings into the rich-text JSON structure used by the DB."""
    if isinstance(value, dict) and "text" in value:
        return value
    if isinstance(value, (list, dict)):
        try:
            value = json.dumps(value, ensure_ascii=False, indent=2)
        except Exception:
            value = str(value)
    return ai_text_to_rtf_json(str(value) if value is not None else "")


def to_list(value) -> list[str]:
    """Normalize common list-shaped values into a list of strings."""
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if item is not None and str(item).strip()]
    if isinstance(value, dict):
        return [str(item).strip() for item in value.values() if item is not None and str(item).strip()]
    if isinstance(value, str):
        parts = []
        for line in value.splitlines():
            for part in line.split(","):
                cleaned = part.strip()
                if cleaned:
                    parts.append(cleaned)
        return parts
    cleaned = str(value).strip()
    return [cleaned] if cleaned else []
