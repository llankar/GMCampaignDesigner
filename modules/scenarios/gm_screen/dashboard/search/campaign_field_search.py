from __future__ import annotations

from typing import Any


def normalize_query(query: str | None) -> str:
    return (query or "").strip().lower()


def build_field_search_index(fields: list[dict[str, Any]]) -> list[dict[str, Any]]:
    indexed_fields: list[dict[str, Any]] = []
    for field in fields:
        searchable_chunks = [str(field.get("name") or "")]

        if field.get("type") == "list":
            searchable_chunks.extend(str(value or "") for value in field.get("values", []))
        else:
            searchable_chunks.append(str(field.get("value") or ""))

        searchable_text = "\n".join(chunk for chunk in searchable_chunks if chunk).lower()
        indexed_fields.append({"field": field, "searchable_text": searchable_text})

    return indexed_fields


def find_match_ranges(text: str, query: str | None) -> list[tuple[int, int]]:
    normalized_query = normalize_query(query)
    if not text or not normalized_query:
        return []

    lowered = text.lower()
    ranges: list[tuple[int, int]] = []
    start = 0

    while True:
        pos = lowered.find(normalized_query, start)
        if pos < 0:
            break
        end = pos + len(normalized_query)
        ranges.append((pos, end))
        start = end

    return ranges
