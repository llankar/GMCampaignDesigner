"""Host management utilities for virtual desk tab placement."""

from __future__ import annotations

from typing import Any

from .zone_helpers import sanitize_tab_zone


class VirtualDeskHostManager:
    """Maintain persistent virtual desk hosts and safely move tab frames."""

    def __init__(self, hosts: dict[str, Any] | None = None):
        self._hosts: dict[str, Any] = {}
        if hosts:
            self.update_hosts(hosts)

    def update_hosts(self, hosts: dict[str, Any]) -> None:
        """Refresh known hosts."""
        self._hosts = {str(zone): host for zone, host in (hosts or {}).items() if host is not None}

    def resolve_zone(self, zone: str | None, *, fallback: str = "center") -> str:
        """Resolve zone against available hosts with robust fallback to center."""
        safe_fallback = sanitize_tab_zone(fallback, fallback="center")
        requested = sanitize_tab_zone(zone, fallback=safe_fallback)
        if requested in self._hosts:
            return requested
        if "center" in self._hosts:
            return "center"
        if safe_fallback in self._hosts:
            return safe_fallback
        if self._hosts:
            return next(iter(self._hosts.keys()))
        return "center"

    def host_for_zone(self, zone: str | None, *, fallback: str = "center") -> Any:
        """Return host object for zone using robust fallback resolution."""
        resolved = self.resolve_zone(zone, fallback=fallback)
        return self._hosts.get(resolved)

    def move_content_frame(self, frame: Any, zone: str | None, *, fallback: str = "center") -> str:
        """Move a content frame into the resolved host zone."""
        resolved = self.resolve_zone(zone, fallback=fallback)
        host = self._hosts.get(resolved)
        if frame is None or host is None:
            return self.resolve_zone("center", fallback=resolved)
        try:
            frame.pack_forget()
            frame.pack(in_=host, fill="both", expand=True)
            return resolved
        except Exception:
            fallback_zone = self.resolve_zone("center", fallback=resolved)
            fallback_host = self._hosts.get(fallback_zone)
            if fallback_host is None:
                return fallback_zone
            try:
                frame.pack_forget()
                frame.pack(in_=fallback_host, fill="both", expand=True)
            except Exception:
                pass
            return fallback_zone
