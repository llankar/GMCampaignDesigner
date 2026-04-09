"""Compatibility facade for legacy imports.

New workspace logic lives in state.layout_state/layout_reducer/layout_serializer.
"""

from __future__ import annotations

from modules.scenarios.gm_screen2.state.layout_serializer import deserialize_layout, serialize_layout


class DesktopLayoutEngine:
    """Legacy shim exposing serialize helpers for tests and adapters."""

    def serialize(self, layout_state):
        return serialize_layout(layout_state)

    def deserialize(self, data):
        return deserialize_layout(data)
