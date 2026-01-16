from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, List, Tuple

from modules.helpers.logging_helper import log_info, log_warning


@dataclass
class TextChunk:
    label: str
    text: str
    start_token: int
    end_token: int


def _strip_code_fences(text: str) -> str:
    if not text:
        return ""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:[a-zA-Z]+)?", "", cleaned, flags=re.IGNORECASE).strip()
        cleaned = cleaned.rstrip("`").strip()
    return cleaned


def _chunk_words(words: List[str], start_offset: int, label_prefix: str, *, max_tokens: int) -> Iterable[TextChunk]:
    cursor = 0
    index = 1
    while cursor < len(words):
        window = words[cursor: cursor + max_tokens]
        start = start_offset + cursor
        end = start + len(window) - 1
        label = f"{label_prefix} {index}" if len(words) > max_tokens else label_prefix
        yield TextChunk(label=label, text=" ".join(window), start_token=start, end_token=end)
        cursor += max_tokens
        index += 1


def split_text_into_chunks(raw_text: str, *, max_tokens: int = 800, page_delimiter: str = "\f") -> List[TextChunk]:
    """Split text by pages (if present) or fall back to fixed token windows."""
    if not raw_text:
        return []

    if page_delimiter in raw_text:
        pages = raw_text.split(page_delimiter)
        chunks: List[TextChunk] = []
        word_offset = 0
        for page_no, page_text in enumerate(pages, start=1):
            page_words = page_text.split()
            chunks.extend(
                _chunk_words(page_words, word_offset, f"Page {page_no}", max_tokens=max_tokens)
            )
            word_offset += len(page_words)
        return chunks

    words = raw_text.split()
    return list(_chunk_words(words, 0, "Chunk", max_tokens=max_tokens))


def summarize_chunks(
    raw_text: str,
    client,
    source_label: str,
    *,
    max_tokens: int = 800,
) -> Tuple[str, List[dict]]:
    """Summarize split chunks and stitch them for downstream prompts."""
    chunks = split_text_into_chunks(raw_text, max_tokens=max_tokens)
    if not chunks:
        return "", []

    stitched_parts: List[str] = []
    metadata: List[dict] = []

    for idx, chunk in enumerate(chunks, start=1):
        log_info(
            f"Summarizing chunk {idx}/{len(chunks)} ({chunk.label})",
            func_name="scenario_chunking.summarize_chunks",
        )
        prompt = (
            "Summarize the following RPG source text chunk.\n"
            "Return 3-6 sentences focusing on concrete events, NPCs, places, and clues.\n"
            "Do not invent facts; rely only on this chunk.\n\n"
            "Keep the original language.\n\n"
            f"Source: {source_label}\n"
            f"Chunk label: {chunk.label} (tokens {chunk.start_token}-{chunk.end_token})\n"
            f"Text:\n{chunk.text}"
        )
        try:
            summary = client.chat([
                {"role": "system", "content": "Summarize RPG source text chunks succinctly. "},
                {"role": "user", "content": prompt},
            ])
        except Exception as exc:
            log_warning(
                f"Chunk {chunk.label} summary failed: {exc}",
                func_name="scenario_chunking.summarize_chunks",
            )
            summary = ""

        clean_summary = _strip_code_fences(summary)
        stitched_parts.append(
            f"{chunk.label} [tokens {chunk.start_token}-{chunk.end_token}]: {clean_summary}"
        )
        metadata.append(
            {
                "label": chunk.label,
                "start_token": chunk.start_token,
                "end_token": chunk.end_token,
                "summary": clean_summary,
            }
        )

    stitched_summary = "\n\n".join(stitched_parts)
    return stitched_summary, metadata
