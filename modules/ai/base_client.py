"""Shared utilities for AI clients."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterable, Mapping, Sequence

from modules.helpers.logging_helper import log_module_import


log_module_import(__name__)


class BaseAIClient(ABC):
    """Common interface implemented by pluggable AI backends."""

    @abstractmethod
    def chat(
        self,
        messages: Sequence[Mapping[str, str]] | str,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        timeout: int = 600,
    ) -> str:
        """Send a chat-style prompt and return the assistant response."""

    @staticmethod
    def format_messages(messages: Sequence[Mapping[str, str]] | str) -> str:
        """Serialize chat messages into a single prompt string."""

        if isinstance(messages, str):
            return messages

        parts: list[str] = []
        for entry in BaseAIClient._iter_messages(messages):
            role = entry.get("role", "user")
            content = entry.get("content", "")
            parts.append(f"{role.capitalize()}: {content}")
        parts.append("Assistant:")
        return "\n".join(parts).strip()

    @staticmethod
    def _iter_messages(messages: Iterable[Mapping[str, str]] | None):
        if not messages:
            return []
        return list(messages)

