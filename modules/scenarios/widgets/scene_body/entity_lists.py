"""Entity list merge helpers for scene body widgets."""

from __future__ import annotations

from typing import Any


def merge_unique_entity_names(*sources: Any) -> list[str]:
    """Merge entity name sources while preserving first-seen display casing."""
    merged: list[str] = []
    seen: set[str] = set()

    for source in sources:
        for item in source or []:
            text = str(item or "").strip()
            if not text:
                continue
            key = text.lower()
            if key in seen:
                continue
            seen.add(key)
            merged.append(text)

    return merged
