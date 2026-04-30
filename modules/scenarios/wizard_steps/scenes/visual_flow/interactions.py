"""Shared interaction helpers for scene and visual flow canvases."""

from __future__ import annotations

import time
from typing import Iterable


def should_open_context_menu(button: int, press_ts: float, release_ts: float, *, threshold_ms: int = 220) -> bool:
    """Return True when a right/middle click should open context menu.

    Mirrors scene editor semantics: open only on quick click, not on press-drag-release.
    """
    if button not in (2, 3):
        return False
    elapsed = max(0.0, release_ts - press_ts) * 1000.0
    return elapsed <= float(threshold_ms)


def now() -> float:
    return time.monotonic()


def normalise_single_selection(selected_id: str | None) -> tuple[str | None, str | None]:
    """Exclusive selection contract: either node or link can be selected."""
    value = str(selected_id or "").strip() or None
    return value, None


def normalise_link_selection(selected_id: str | None) -> tuple[str | None, str | None]:
    """Exclusive selection contract: either link or node can be selected."""
    value = str(selected_id or "").strip() or None
    return None, value


def resolve_link_target(source_id: str, target_candidates: Iterable[str]) -> str | None:
    """Pick the first non-self candidate as link drop target."""
    source = str(source_id or "").strip()
    for candidate in target_candidates:
        target = str(candidate or "").strip()
        if target and target != source:
            return target
    return None
