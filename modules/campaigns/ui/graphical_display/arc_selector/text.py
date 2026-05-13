"""Text fitting helpers for campaign arc selector cards."""

from __future__ import annotations

ELLIPSIS = "..."
MIN_TITLE_CHAR_BUDGET = 14
MAX_TITLE_CHAR_BUDGET = 34
ARC_TITLE_HORIZONTAL_PADDING = 32
SEGEO_UI_BOLD_12_AVERAGE_CHAR_WIDTH = 8.2


def title_limit_for_card_width(width: float) -> int:
    """Estimate the title character budget that fits inside an arc card."""
    usable_width = max(float(width or 0) - ARC_TITLE_HORIZONTAL_PADDING, 0)
    chars_per_line = int(usable_width / SEGEO_UI_BOLD_12_AVERAGE_CHAR_WIDTH)
    bounded_chars = max(chars_per_line, MIN_TITLE_CHAR_BUDGET)
    return min(bounded_chars, MAX_TITLE_CHAR_BUDGET)


def truncate_to_width(value: str, limit: int) -> str:
    """Truncate text to a character budget and append one trailing ellipsis."""
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    if limit <= len(ELLIPSIS):
        return ELLIPSIS[: max(limit, 0)]
    return text[: limit - len(ELLIPSIS)].rstrip() + ELLIPSIS
