from types import SimpleNamespace

from modules.scenarios.wizard_steps.scenes.visual_flow_planner import FlowHierarchyPanel, VisualFlowPlanner


class _TreeStub:
    def __init__(self):
        self._selection = ()

    def selection(self):
        return self._selection


def test_tree_context_dispatches_move_shortcuts_from_selection():
    calls = []
    panel = SimpleNamespace(
        _tree=_TreeStub(),
        _item_to_node_id={"item-1": "node-1"},
        _dispatch_command=lambda command, **kwargs: calls.append((command, kwargs)),
    )
    panel._tree._selection = ("item-1",)

    assert FlowHierarchyPanel._on_move_up_shortcut(panel) == "break"
    assert FlowHierarchyPanel._on_move_down_shortcut(panel) == "break"
    assert calls == [
        ("move_up", {"node_id": "node-1"}),
        ("move_down", {"node_id": "node-1"}),
    ]


def test_tree_reorder_drag_release_dispatches_reorder_command_path():
    calls = []
    panel = SimpleNamespace(
        _tree=object(),
        _dragged_item_id="drag",
        _drop_target_item_id="target",
        _drop_place_after=True,
        _item_to_node_id={"drag": "node-a", "target": "node-b"},
        _dispatch_command=lambda command, **kwargs: calls.append((command, kwargs)),
        _clear_drop_marker=lambda: None,
    )

    FlowHierarchyPanel._on_drag_release(panel, None)

    assert calls == [
        ("reorder", {"node_id": "node-a", "target_node_id": "node-b", "place_after": True})
    ]


def test_visual_planner_routes_context_commands_to_expected_operations():
    calls = []
    planner = SimpleNamespace(
        _node_anchor_context=lambda node_id=None: {"node_id": node_id},
        add_node=lambda node_type, anchor: calls.append(("add", node_type, anchor)),
        delete_node=lambda node_id: calls.append(("delete", node_id)),
        reorder_node=lambda node_id, direction: calls.append(("reorder", node_id, direction)),
        reorder_node_relative=lambda node_id, target_id, place_after=False: calls.append(("reorder_rel", node_id, target_id, place_after)),
        cut_node=lambda node_id: calls.append(("cut", node_id)),
        copy_node=lambda node_id: calls.append(("copy", node_id)),
        paste_node=lambda anchor: calls.append(("paste", anchor)),
    )

    VisualFlowPlanner._handle_hierarchy_command(planner, "move_up", {"node_id": "n1"})
    VisualFlowPlanner._handle_hierarchy_command(planner, "reorder", {"node_id": "n1", "target_node_id": "n2", "place_after": 1})
    VisualFlowPlanner._handle_hierarchy_command(planner, "paste", {"node_id": "n1"})

    assert calls == [
        ("reorder", "n1", "up"),
        ("reorder_rel", "n1", "n2", True),
        ("paste", {"node_id": "n1"}),
    ]
