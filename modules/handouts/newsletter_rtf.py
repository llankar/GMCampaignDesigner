from __future__ import annotations

from typing import Any, Dict, Iterable, List, Tuple

from modules.handouts.newsletter_generator import build_newsletter_payload
from modules.handouts.newsletter_plain_renderer import render_plain_newsletter
from modules.helpers.logging_helper import log_module_import
from modules.helpers.text_helpers import ai_text_to_rtf_json, deserialize_possible_json

log_module_import(__name__)

DEFAULT_FONT = "Arial"
DEFAULT_FONT_SIZE = 12


def _render_newsletter_plain(payload: Dict[str, Iterable[Any]] | None) -> str:
    return render_plain_newsletter(payload)


def _coerce_payload(payload: Any, language: str | None, style: str | None) -> Dict[str, Iterable[Any]]:
    if isinstance(payload, dict):
        scenario_title = payload.get("scenario_title")
        if scenario_title:
            sections = payload.get("sections")
            base_text = payload.get("base_text")
            return build_newsletter_payload(scenario_title, sections, language, style, base_text)
        return payload
    if isinstance(payload, (list, tuple)):
        if not payload:
            return {}
        scenario_title = payload[0]
        sections = payload[1] if len(payload) > 1 else None
        if scenario_title:
            return build_newsletter_payload(scenario_title, sections, language, style)
        return {}
    if isinstance(payload, str) and payload.strip():
        return build_newsletter_payload(payload.strip(), None, language, style)
    return {}


def _escape_rtf(text: str) -> str:
    return text.replace("\\", r"\\").replace("{", r"\{").replace("}", r"\}")


def _build_rtf_events(formatting: Dict[str, Iterable[Tuple[int, int]]]) -> List[Tuple[int, str, str]]:
    events: List[Tuple[int, str, str]] = []
    for tag, ranges in (formatting or {}).items():
        for start, end in ranges:
            try:
                s = int(start)
                e = int(end)
            except (TypeError, ValueError):
                continue
            if e <= s:
                continue
            events.append((s, "open", tag))
            events.append((e, "close", tag))
    events.sort(key=lambda item: (item[0], 0 if item[1] == "close" else 1))
    return events


def _rtf_control_for_tag(tag: str, is_open: bool, default_size: int) -> str:
    if tag == "bold":
        return "\\b" if is_open else "\\b0"
    if tag == "italic":
        return "\\i" if is_open else "\\i0"
    if tag == "underline":
        return "\\ul" if is_open else "\\ul0"
    if tag.startswith("size_"):
        if is_open:
            try:
                size = int(tag.split("_", 1)[1])
            except (ValueError, IndexError):
                size = default_size
            return f"\\fs{size * 2}"
        return f"\\fs{default_size * 2}"
    return ""


def rtf_json_to_rtf_string(rtf_json: Dict[str, Any], font_name: str = DEFAULT_FONT, font_size: int = DEFAULT_FONT_SIZE) -> str:
    text = str(rtf_json.get("text", ""))
    formatting = rtf_json.get("formatting", {}) if isinstance(rtf_json, dict) else {}
    events = _build_rtf_events(formatting)

    header = f"{{\\rtf1\\ansi\\deff0{{\\fonttbl{{\\f0 {font_name};}}}}\\fs{font_size * 2} "
    parts: List[str] = [header]

    event_index = 0
    for idx in range(len(text) + 1):
        while event_index < len(events) and events[event_index][0] == idx:
            _, kind, tag = events[event_index]
            control = _rtf_control_for_tag(tag, kind == "open", font_size)
            if control:
                parts.append(control + " ")
            event_index += 1

        if idx == len(text):
            break
        char = text[idx]
        if char == "\n":
            parts.append("\\line ")
        else:
            parts.append(_escape_rtf(char))

    parts.append("}")
    return "".join(parts)


def build_newsletter_rtf_json_from_payload(
    payload: Any,
    language: str | None = None,
    style: str | None = None,
) -> Dict[str, Any]:
    resolved_payload = _coerce_payload(payload, language, style)
    plain_text = _render_newsletter_plain(resolved_payload)
    return ai_text_to_rtf_json(plain_text)


def build_newsletter_rtf_json_from_ai_text(raw_text: Any) -> Dict[str, Any]:
    parsed = deserialize_possible_json(raw_text)
    if isinstance(parsed, dict) and ("text" in parsed or "formatting" in parsed):
        return parsed
    return ai_text_to_rtf_json(str(parsed or ""))


def build_newsletter_rtf_from_payload(payload: Any, language: str | None = None, style: str | None = None) -> str:
    return rtf_json_to_rtf_string(
        build_newsletter_rtf_json_from_payload(payload, language, style),
    )


def build_newsletter_rtf_from_ai_text(raw_text: Any) -> str:
    return rtf_json_to_rtf_string(build_newsletter_rtf_json_from_ai_text(raw_text))
