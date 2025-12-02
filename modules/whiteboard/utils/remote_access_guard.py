import hmac
from typing import Optional

from modules.helpers.config_helper import ConfigHelper


class RemoteAccessGuard:
    """Small helper to gate remote whiteboard edits behind a GM token and runtime toggle."""

    def __init__(self, *, enabled: bool = False, token: Optional[str] = None):
        self._enabled = bool(enabled)
        self._token = (token or "").strip()

    @classmethod
    def from_config(cls, enabled: bool = False) -> "RemoteAccessGuard":
        token = str(ConfigHelper.get("WhiteboardServer", "gm_token", fallback="") or "")
        return cls(enabled=enabled, token=token)

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def token(self) -> str:
        return self._token

    def set_enabled(self, value: bool) -> None:
        self._enabled = bool(value)

    def is_request_authorized(self, provided_token: Optional[str]) -> bool:
        if not self._enabled:
            return False
        if not self._token:
            # If no token is configured, treat the session toggle alone as authorization.
            return True
        if provided_token is None:
            return False
        try:
            return hmac.compare_digest(self._token, str(provided_token))
        except Exception:
            return False

