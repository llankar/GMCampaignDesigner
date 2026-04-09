"""Workspace mounting tests for GM Screen 2 panel zones."""

from modules.scenarios.gm_screen2.state.layout_reducer import find_zone
from modules.scenarios.gm_screen2.state.layout_state import LayoutState


def test_panel_mount_unmount_in_workspace_zones():
    state = LayoutState()
    left = find_zone(state.root, "zone_left")

    assert left is not None
    assert "overview" in left.panel_stack

    left.panel_stack.remove("overview")
    assert "overview" not in left.panel_stack
