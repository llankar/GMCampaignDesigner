from __future__ import annotations

from modules.core.ai.state.request_state import AIRequestState


class AIRunWindowViewModel:
    @staticmethod
    def title(state: AIRequestState) -> str:
        if state.request_id:
            return f"AI Run · {state.request_id[:8]}"
        return "AI Run"

    @staticmethod
    def phase_text(state: AIRequestState) -> str:
        return state.phase_text or "Idle"
