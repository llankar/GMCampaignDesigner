"""Display text guards for the campaign graphical overview."""
from __future__ import annotations

from modules.helpers.tk_text_safety import (
    DEFAULT_DISPLAY_LIMIT,
    ELLIPSIS,
    LABEL_DISPLAY_LIMIT,
    LIST_ITEM_DISPLAY_LIMIT,
    LONGFORM_DISPLAY_LIMIT,
    MAX_LIST_ITEMS,
    safe_display_list,
    safe_display_text,
    truncate_display_text,
)

__all__ = [
    "DEFAULT_DISPLAY_LIMIT",
    "ELLIPSIS",
    "LABEL_DISPLAY_LIMIT",
    "LIST_ITEM_DISPLAY_LIMIT",
    "LONGFORM_DISPLAY_LIMIT",
    "MAX_LIST_ITEMS",
    "safe_display_list",
    "safe_display_text",
    "truncate_display_text",
]
