"""Backwards-compatible exports for tab UI positioning metadata helpers."""

from modules.scenarios.gm_screen.virtual_desk.zone_helpers import (
    VALID_TAB_ZONES,
    apply_tab_zone_metadata,
    sanitize_tab_zone,
)

__all__ = ["VALID_TAB_ZONES", "sanitize_tab_zone", "apply_tab_zone_metadata"]
