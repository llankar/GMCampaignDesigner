"""Utility helpers for working with list-like collections."""

from __future__ import annotations

from typing import Dict, Iterable, List, Mapping, Sequence, Tuple, TypeVar

from modules.helpers.logging_helper import log_module_import

log_module_import(__name__)


T = TypeVar("T")


def dedupe_preserve_case(values: Iterable[T]) -> Tuple[List[T], Dict[T, List[T]]]:
    """Return the values with case-folded duplicates removed.

    The first encountered casing of each distinct string is preserved in the
    output list.  Any subsequent values that match when compared using
    :meth:`str.casefold` are collected and returned so callers can notify users
    about collapsed duplicates.
    """

    result: List[T] = []
    seen: Dict[str, T] = {}
    duplicates: Dict[T, List[T]] = {}

    for value in values:
        if isinstance(value, str):
            key = value.casefold()
        else:
            key = str(value).casefold()

        if key not in seen:
            seen[key] = value
            result.append(value)
            continue

        canonical = seen[key]
        duplicates.setdefault(canonical, []).append(value)

    return result, duplicates


def _format_duplicate_line(canonical: str, duplicates: Sequence[str]) -> str:
    unique_duplicates: List[str] = []
    for dup in duplicates:
        dup_str = str(dup)
        if dup_str not in unique_duplicates:
            unique_duplicates.append(dup_str)

    canonical_str = str(canonical)
    duplicates_display = ", ".join(unique_duplicates)

    if duplicates_display and duplicates_display == canonical_str:
        return f"• {canonical_str} (duplicate removed)"

    if duplicates_display:
        return f"• {duplicates_display} → {canonical_str}"

    return f"• {canonical_str} (duplicate removed)"


def format_duplicate_summary(
    field_label: str,
    duplicates: Mapping[str, Sequence[str]],
    intro: str | None = None,
) -> str:
    """Build a human-readable explanation for collapsed duplicates."""

    if not duplicates:
        return ""

    lines: List[str] = []
    if intro:
        intro = intro.strip()
        if intro:
            lines.append(intro)
            lines.append("")

    lines.append(
        f"The following {field_label} entries were merged because they only differed by letter case:"
    )
    for canonical, dupes in duplicates.items():
        lines.append(_format_duplicate_line(str(canonical), dupes))

    return "\n".join(lines)


def format_multi_field_duplicate_summary(
    field_to_duplicates: Mapping[str, Mapping[str, Sequence[str]]],
    intro: str | None = None,
) -> str:
    """Combine duplicate summaries from multiple fields into a single message."""

    sections: List[str] = []
    for field, duplicates in field_to_duplicates.items():
        summary = format_duplicate_summary(field, duplicates)
        if summary:
            sections.append(summary)

    if not sections:
        return ""

    body = "\n\n".join(sections)
    if intro:
        intro = intro.strip()
        if intro:
            return f"{intro}\n\n{body}"

    return body
