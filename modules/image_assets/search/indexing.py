"""Normalization and indexing helpers for image-asset search."""

from __future__ import annotations

from collections.abc import Iterable
import re

_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def normalize_query(query: str | None) -> str:
    """Normalize free-form user query into a compact lowercase expression."""
    return " ".join(_NON_ALNUM.sub(" ", str(query or "").lower()).split())


def tokenize_query(query: str | None) -> list[str]:
    """Tokenize query into deterministic terms for lookup/matching."""
    normalized = normalize_query(query)
    if not normalized:
        return []
    return [token for token in normalized.split(" ") if token]


def normalize_filename(name: str | None) -> str:
    """Normalize filename-like values while preserving lexical matching behavior."""
    return normalize_query(name)


def normalize_tag(tag: str | None) -> str:
    """Normalize one tag value."""
    return normalize_query(tag)


def normalize_extension(extension: str | None) -> str:
    """Normalize extension and remove leading dot."""
    raw = str(extension or "").strip().lower()
    return raw[1:] if raw.startswith(".") else raw


def build_search_tokens(*, name_normalized: str, tags: Iterable[str]) -> list[str]:
    """Build deterministic search tokens from normalized name and tags."""
    ordered: list[str] = []

    def _add(token: str) -> None:
        token = token.strip()
        if token and token not in ordered:
            ordered.append(token)

    if name_normalized:
        for part in name_normalized.split():
            _add(part)
        _add(name_normalized.replace(" ", ""))

    for tag in tags:
        normalized = normalize_tag(tag)
        if not normalized:
            continue
        for part in normalized.split():
            _add(part)
        _add(normalized.replace(" ", ""))

    return ordered


def build_searchable_blob(
    *,
    name: str | None,
    path: str | None,
    relative_path: str | None,
    source_root: str | None,
    extension: str | None,
    tags: Iterable[str],
    name_normalized: str | None,
    search_tokens: Iterable[str],
    source_folder_name: str | None = None,
) -> str:
    """Build a lowercased precomputed blob used by fast in-memory matching."""
    chunks: list[str] = [
        str(name or ""),
        str(path or ""),
        str(relative_path or ""),
        str(source_root or ""),
        str(source_folder_name or ""),
        str(extension or ""),
        str(name_normalized or ""),
    ]
    chunks.extend(str(tag or "") for tag in tags)
    chunks.extend(str(token or "") for token in search_tokens)
    return "\n".join(chunk.lower() for chunk in chunks if chunk)
