import json
import re
from typing import Any

from modules.helpers.logging_helper import log_module_import

log_module_import(__name__)


def parse_ai_json(payload: str) -> Any:
    if not payload:
        raise RuntimeError("Empty AI response")
    text = payload.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(json)?", "", text, flags=re.IGNORECASE).strip()
        text = text.rstrip("`").strip()
    try:
        return json.loads(text)
    except Exception:
        pass

    start = None
    for idx, ch in enumerate(text):
        if ch in "{[":
            start = idx
            break
    if start is None:
        raise RuntimeError("Failed to parse JSON from AI response")

    tail = text[start:]
    for end in range(len(tail), max(len(tail) - 2000, 0), -1):
        chunk = tail[:end]
        try:
            return json.loads(chunk)
        except Exception:
            continue

    raise RuntimeError("Failed to parse JSON from AI response")
