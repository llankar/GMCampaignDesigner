"""Display text guards for the campaign graphical overview."""
from __future__ import annotations

from typing import Any

from modules.helpers.text_helpers import coerce_text

ELLIPSIS = "…"
DEFAULT_DISPLAY_LIMIT = 8_000
LABEL_DISPLAY_LIMIT = 240
LONGFORM_DISPLAY_LIMIT = 6_000
LIST_ITEM_DISPLAY_LIMIT = 240
MAX_LIST_ITEMS = 200


def safe_display_text(value: Any, *, max_chars: int = DEFAULT_DISPLAY_LIMIT) -> str:
    """Return plain text bounded to a size Tk can safely render.

    Imported campaign data can contain accidentally huge blobs (for example a
    pasted PDF, serialized rich-text payload, or binary-ish field). Passing those
    values directly into Tk label/button/menu text can surface later from
    ``mainloop`` as ``OverflowError: string is too long``. This helper keeps the
    overview readable while preserving enough content to identify the record.
    """

    text = coerce_text(value).strip()
    return truncate_display_text(text, max_chars=max_chars)


def truncate_display_text(value: Any, *, max_chars: int = DEFAULT_DISPLAY_LIMIT) -> str:
    """Truncate ``value`` to ``max_chars`` with a visible ellipsis marker."""

    text = str(value or "")
    if max_chars < 1:
        return ""
    if len(text) <= max_chars:
        return text
    suffix = f" {ELLIPSIS}"
    keep = max(max_chars - len(suffix), 0)
    return text[:keep].rstrip() + suffix


def safe_display_list(
    value: Any,
    *,
    max_items: int = MAX_LIST_ITEMS,
    item_max_chars: int = LIST_ITEM_DISPLAY_LIMIT,
) -> list[str]:
    """Return a de-duplicated, bounded list of safe display strings."""

    if not isinstance(value, list):
        return []

    result: list[str] = []
    for entry in value:
        text = safe_display_text(entry, max_chars=item_max_chars)
        if text and text not in result:
            result.append(text)
        if len(result) >= max_items:
            break
    return result
