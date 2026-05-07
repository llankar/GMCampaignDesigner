"""Width helpers for compact floating toolbar controls."""

from __future__ import annotations

CONTROL_TEXT_PIXEL_WIDTH = 7
CONTROL_HORIZONTAL_PADDING = 18
CONTROL_MIN_WIDTH = 34


def width_for_display_text(text: object) -> int:
    """Return a compact control width sized to the currently displayed text."""
    display_text = str(text or "")
    return max(CONTROL_MIN_WIDTH, len(display_text) * CONTROL_TEXT_PIXEL_WIDTH + CONTROL_HORIZONTAL_PADDING)
