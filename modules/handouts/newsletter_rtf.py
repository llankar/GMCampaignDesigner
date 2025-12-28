from __future__ import annotations

from typing import Any, Dict, Iterable, List, Tuple

from modules.handouts.newsletter_generator import build_newsletter_payload
from modules.helpers.logging_helper import log_module_import
from modules.helpers.text_helpers import ai_text_to_rtf_json, deserialize_possible_json

log_module_import(__name__)

DEFAULT_FONT = "Arial"
DEFAULT_FONT_SIZE = 12


def _format_item_line(item: Any) -> str | None:
    if isinstance(item, dict):
        title = str(item.get("Title") or item.get("Name") or "").strip()
        text = str(item.get("Text") or item.get("Description") or "").strip()
        if title and text:
            return f"- {title}: {text}"
        if title:
            return f"- {title}"
        if text:
            return f"- {text}"
        related = item.get("Related")
        if isinstance(related, dict) and related:
            related_parts = []
            for key, entries in related.items():
                names = []
                for entry in entries or []:
                    if isinstance(entry, dict) and entry.get("Name"):
                        names.append(str(entry.get("Name")).strip())
                    elif entry:
                        names.append(str(entry).strip())
                if names:
                    related_parts.append(f"{key}: {', '.join(names)}")
            if related_parts:
                return f"- Related: {'; '.join(related_parts)}"
        return None
    if item is None:
        return None
    text = str(item).strip()
    return f"- {text}" if text else None


def _render_newsletter_markdown(payload: Dict[str, Iterable[Any]] | None, language: str | None, style: str | None) -> str:
    lines: List[str] = ["# Newsletter"]
    meta_parts = []
    if language:
        meta_parts.append(f"Langue: {language}")
    if style:
        meta_parts.append(f"Style: {style}")
    if meta_parts:
        lines.append(f"*{' - '.join(meta_parts)}*")

    for section_name, items in (payload or {}).items():
        if not items:
            continue
        lines.append("")
        lines.append(f"## {section_name}")
        for item in items:
            line = _format_item_line(item)
            if line:
                lines.append(line)
    return "\n".join(lines).strip()


def _coerce_payload(payload: Any, language: str | None, style: str | None) -> Dict[str, Iterable[Any]]:
    if isinstance(payload, dict):
        scenario_title = payload.get("scenario_title")
        if scenario_title:
            sections = payload.get("sections")
            return build_newsletter_payload(scenario_title, sections, language, style)
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
    markdown_text = _render_newsletter_markdown(resolved_payload, language, style)
    return ai_text_to_rtf_json(markdown_text)


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
