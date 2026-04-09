"""Zone and metadata helpers for the GM Screen virtual desk UI."""

from __future__ import annotations


VALID_TAB_ZONES = {"center", "right", "bottom"}


def sanitize_tab_zone(zone: str | None, *, fallback: str = "center") -> str:
    """Return a safe tab zone with fallback when the requested zone is invalid."""
    safe_fallback = str(fallback or "center").strip().lower()
    if safe_fallback not in VALID_TAB_ZONES:
        safe_fallback = "center"
    normalized = str(zone or "").strip().lower()
    if normalized in VALID_TAB_ZONES:
        return normalized
    return safe_fallback


def apply_tab_zone_metadata(meta: dict | None, zone: str | None, *, fallback: str = "center") -> str:
    """Update tab metadata with a safe UI zone and derived state."""
    payload = meta if isinstance(meta, dict) else {}
    safe_zone = sanitize_tab_zone(zone, fallback=fallback)
    payload["ui_zone"] = safe_zone
    payload["ui_state"] = "normal" if safe_zone == "center" else "docked"
    return safe_zone
