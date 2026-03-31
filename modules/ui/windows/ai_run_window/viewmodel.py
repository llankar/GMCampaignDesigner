"""Utilities for AI run window viewmodel."""

from __future__ import annotations

from modules.core.ai.state.request_state import AIRequestState


class AIRunWindowViewModel:
    @staticmethod
    def title(state: AIRequestState) -> str:
        """Handle title."""
        if state.request_id:
            return f"AI Run · {state.request_id[:8]}"
        return "AI Run"

    @staticmethod
    def phase_text(state: AIRequestState) -> str:
        """Handle phase text."""
        return state.phase_text or "Idle"
