"""Helpers for image import root selection and validation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass(slots=True)
class RootValidationResult:
    """Validated roots separated between existing and missing folders."""

    existing_roots: list[str]
    missing_roots: list[str]


def normalize_roots(paths: Iterable[str]) -> list[str]:
    """Normalize, trim, resolve, and dedupe root candidates preserving order."""
    deduped: list[str] = []
    seen: set[str] = set()

    for raw in paths:
        candidate = str(raw or "").strip()
        if not candidate:
            continue
        normalized = str(Path(candidate).expanduser().resolve())
        if normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(normalized)

    return deduped


def merge_roots(existing: Iterable[str], incoming: Iterable[str]) -> list[str]:
    """Return normalized existing roots extended by incoming non-duplicates."""
    return normalize_roots([*list(existing), *list(incoming)])


def validate_roots(paths: Iterable[str]) -> RootValidationResult:
    """Partition normalized roots between existing and missing directories."""
    existing: list[str] = []
    missing: list[str] = []

    for root in normalize_roots(paths):
        path = Path(root)
        if path.exists() and path.is_dir():
            existing.append(root)
        else:
            missing.append(root)

    return RootValidationResult(existing_roots=existing, missing_roots=missing)
