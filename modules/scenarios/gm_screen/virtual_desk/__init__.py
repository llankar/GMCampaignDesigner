"""UI helpers for GM Screen virtual desk orchestration."""

from .host_manager import VirtualDeskHostManager
from .zone_helpers import VALID_TAB_ZONES, apply_tab_zone_metadata, sanitize_tab_zone

__all__ = [
    "VALID_TAB_ZONES",
    "VirtualDeskHostManager",
    "apply_tab_zone_metadata",
    "sanitize_tab_zone",
]
