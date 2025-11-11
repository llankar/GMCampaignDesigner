"""Factory helpers for creating AI clients based on configuration."""

from __future__ import annotations

from modules.ai.local_ai_client import LocalAIClient
from modules.helpers.config_helper import ConfigHelper
from modules.helpers.logging_helper import log_module_import

log_module_import(__name__)


def create_ai_client():
    backend = ConfigHelper.get("AI", "backend", fallback="local")
    backend = (backend or "local").strip().lower()

    if backend == "web":
        from modules.ai.web_ai_client import WebAIClient

        return WebAIClient()

    return LocalAIClient()

