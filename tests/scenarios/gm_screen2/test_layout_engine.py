"""Tests for GM Screen 2 workspace layout serialization."""

from modules.scenarios.gm_screen2.state.layout_serializer import deserialize_layout, serialize_layout
from modules.scenarios.gm_screen2.state.layout_state import LayoutState, SplitNode


def test_layout_tree_serialization_round_trip_preserves_nested_splits():
    state = LayoutState()

    serialized = serialize_layout(state)
    loaded = deserialize_layout(serialized)

    assert isinstance(loaded.root, SplitNode)
    assert serialize_layout(loaded) == serialized
