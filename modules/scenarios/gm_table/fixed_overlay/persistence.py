"""Persistence helpers for the fixed overlay."""
from __future__ import annotations
from typing import Any
from .models import FixedOverlayState


def serialize_state(state: FixedOverlayState | dict[str, Any] | None) -> dict[str, Any]:
    if isinstance(state, FixedOverlayState):
        return state.to_dict()
    return FixedOverlayState.from_dict(state if isinstance(state, dict) else {}).to_dict()


def restore_state(payload: dict[str, Any] | None) -> FixedOverlayState:
    return FixedOverlayState.from_dict(payload)
