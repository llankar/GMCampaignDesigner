"""Path normalization helpers for report payloads."""

from __future__ import annotations


def normalize_report_paths(paths: list[str] | None) -> list[str]:
    """Normalize report paths to forward-slash notation."""
    normalized: list[str] = []
    for path in paths or []:
        if not isinstance(path, str):
            continue
        cleaned = path.strip()
        if not cleaned:
            continue
        normalized.append(cleaned.replace("\\", "/"))

    return normalized
