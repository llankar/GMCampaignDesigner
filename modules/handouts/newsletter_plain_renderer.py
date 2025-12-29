from __future__ import annotations

from typing import Any, Dict, Iterable, List, Sequence

from modules.helpers.logging_helper import log_module_import

log_module_import(__name__)

SUMMARY_KEYS = {"summary", "résumé", "resume"}
SCENE_KEYS = {"scenes", "scènes", "scene", "scène"}
BASE_KEYS = {"base", "récit", "recit", "recap", "chronique"}
ENTITY_KEYS = {
    "npcs",
    "pnjs",
    "personnages",
    "places",
    "lieux",
    "factions",
    "items",
    "objets",
    "threats",
    "menaces",
    "clues",
    "indices",
    "rewards",
    "récompenses",
}


def _ensure_sentence(text: str) -> str:
    cleaned = text.strip()
    if not cleaned:
        return ""
    if cleaned[-1] not in ".!?…":
        cleaned += "."
    return cleaned


def _related_summary(related: Dict[str, Iterable[Any]]) -> str:
    related_parts = []
    for key, entries in related.items():
        names = []
        for entry in entries or []:
            if isinstance(entry, dict) and entry.get("Name"):
                names.append(str(entry.get("Name")).strip())
            elif entry:
                names.append(str(entry).strip())
        names = [name for name in names if name]
        if names:
            related_parts.append(f"{key}: {', '.join(names)}")
    if related_parts:
        return "Liens mentionnés : " + "; ".join(related_parts)
    return ""


def _extract_item_sentences(item: Any) -> List[str]:
    if item is None:
        return []
    if isinstance(item, dict):
        title = str(item.get("Title") or item.get("Name") or "").strip()
        text = str(item.get("Text") or item.get("Description") or item.get("Summary") or "").strip()
        if title and text:
            return [_ensure_sentence(f"{title} : {text}")]
        if text:
            return [_ensure_sentence(text)]
        if title:
            return [_ensure_sentence(title)]
        related = item.get("Related")
        if isinstance(related, dict) and related:
            summary = _related_summary(related)
            if summary:
                return [_ensure_sentence(summary)]
        return []
    if isinstance(item, (list, tuple)):
        sentences = []
        for entry in item:
            sentences.extend(_extract_item_sentences(entry))
        return sentences
    text = str(item).strip()
    return [_ensure_sentence(text)] if text else []


def _collect_section_sentences(items: Iterable[Any] | None) -> List[str]:
    sentences: List[str] = []
    for item in items or []:
        sentences.extend(_extract_item_sentences(item))
    return [sentence for sentence in sentences if sentence]


def _find_section_items(payload: Dict[str, Iterable[Any]], keys: Sequence[str]) -> tuple[str, Iterable[Any]] | None:
    for section_name, items in payload.items():
        if str(section_name).strip().lower() in keys:
            return section_name, items
    return None


def _build_paragraphs(sentences: List[str]) -> List[str]:
    if not sentences:
        return []
    paragraph_count = 3 if len(sentences) <= 6 else 4
    starters = [
        "Dans les rues et les tavernes, les nouvelles du jour retiennent l'attention.",
        "Les derniers événements ont laissé des traces visibles.",
        "Au fil des témoignages, plusieurs noms et lieux reviennent.",
        "En toile de fond, les rumeurs continuent de se propager.",
    ]
    chunks: List[List[str]] = [[] for _ in range(paragraph_count)]
    for idx, sentence in enumerate(sentences):
        chunks[idx % paragraph_count].append(sentence)
    paragraphs = []
    for idx, chunk in enumerate(chunks):
        starter = starters[idx] if idx < len(starters) else "La chronique du jour se poursuit."
        content = " ".join(chunk).strip()
        paragraph = f"{starter} {content}".strip() if content else starter
        paragraphs.append(paragraph.strip())
    return paragraphs


def render_plain_newsletter(payload: Dict[str, Iterable[Any]] | None) -> str:
    if not payload:
        return ""

    base_section = _find_section_items(payload, BASE_KEYS)
    summary_section = _find_section_items(payload, SUMMARY_KEYS)
    scene_section = _find_section_items(payload, SCENE_KEYS)
    entity_section = _find_section_items(payload, ENTITY_KEYS)

    used_keys = {section[0] for section in [base_section, summary_section, scene_section, entity_section] if section}

    base_sentences: List[str] = []
    if base_section:
        base_sentences = _collect_section_sentences(base_section[1])

    sentences: List[str] = []
    if summary_section:
        sentences.extend(_collect_section_sentences(summary_section[1]))
    if scene_section:
        sentences.extend(_collect_section_sentences(scene_section[1]))
    if entity_section:
        sentences.extend(_collect_section_sentences(entity_section[1]))

    for section_name, items in payload.items():
        if section_name in used_keys:
            continue
        sentences.extend(_collect_section_sentences(items))

    sentences = [sentence for sentence in sentences if sentence]
    paragraphs = _build_paragraphs(sentences)
    base_paragraph = " ".join(base_sentences).strip() if base_sentences else ""
    if base_paragraph:
        paragraphs = [base_paragraph] + paragraphs
    return "\n\n".join([p for p in paragraphs if p]).strip()
