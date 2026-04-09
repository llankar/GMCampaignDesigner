"""Reducer-like operations for mutating workspace layout state."""

from __future__ import annotations

from dataclasses import replace

from modules.scenarios.gm_screen2.state.layout_state import LayoutNode, LayoutState, SplitNode, ZoneNode


def move_panel(layout: LayoutState, panel_id: str, target_zone_id: str, index: int | None = None) -> None:
    source = find_zone_with_panel(layout.root, panel_id)
    target = find_zone(layout.root, target_zone_id)
    if source is None or target is None:
        return
    if panel_id in source.panel_stack:
        source.panel_stack.remove(panel_id)
    if index is None or index >= len(target.panel_stack):
        target.panel_stack.append(panel_id)
    else:
        target.panel_stack.insert(max(0, index), panel_id)
    target.active_panel_id = panel_id


def split_zone(layout: LayoutState, zone_id: str, axis: str, new_zone_id: str, moved_panel_id: str | None = None) -> None:
    target = find_zone(layout.root, zone_id)
    if target is None:
        return
    new_stack: list[str] = []
    if moved_panel_id and moved_panel_id in target.panel_stack:
        target.panel_stack.remove(moved_panel_id)
        new_stack.append(moved_panel_id)
    replacement = SplitNode(
        id=f"split_{zone_id}_{new_zone_id}",
        axis="vertical" if axis == "vertical" else "horizontal",
        ratio=0.5,
        first=target,
        second=ZoneNode(id=new_zone_id, panel_stack=new_stack, active_panel_id=(new_stack[0] if new_stack else None)),
    )
    layout.root = _replace_node(layout.root, zone_id, replacement)


def merge_zone(layout: LayoutState, zone_id: str, into_zone_id: str) -> None:
    src = find_zone(layout.root, zone_id)
    dst = find_zone(layout.root, into_zone_id)
    if src is None or dst is None or src is dst:
        return
    for panel_id in src.panel_stack:
        if panel_id not in dst.panel_stack:
            dst.panel_stack.append(panel_id)
    layout.root = _prune_zone(layout.root, zone_id)


def resize_split(layout: LayoutState, split_id: str, ratio: float) -> None:
    split = find_split(layout.root, split_id)
    if split is not None:
        split.ratio = min(0.9, max(0.1, float(ratio)))


def toggle_visibility(layout: LayoutState, panel_id: str) -> None:
    panel = layout.panel_instances.get(panel_id)
    if panel is not None:
        panel.visible = not panel.visible


def find_zone(node: LayoutNode, zone_id: str) -> ZoneNode | None:
    if isinstance(node, ZoneNode):
        return node if node.id == zone_id else None
    return find_zone(node.first, zone_id) or find_zone(node.second, zone_id)


def find_zone_with_panel(node: LayoutNode, panel_id: str) -> ZoneNode | None:
    if isinstance(node, ZoneNode):
        return node if panel_id in node.panel_stack else None
    return find_zone_with_panel(node.first, panel_id) or find_zone_with_panel(node.second, panel_id)


def find_split(node: LayoutNode, split_id: str) -> SplitNode | None:
    if isinstance(node, ZoneNode):
        return None
    if node.id == split_id:
        return node
    return find_split(node.first, split_id) or find_split(node.second, split_id)


def _replace_node(node: LayoutNode, zone_id: str, replacement: LayoutNode) -> LayoutNode:
    if isinstance(node, ZoneNode):
        return replacement if node.id == zone_id else node
    node.first = _replace_node(node.first, zone_id, replacement)
    node.second = _replace_node(node.second, zone_id, replacement)
    return node


def _prune_zone(node: LayoutNode, zone_id: str) -> LayoutNode:
    if isinstance(node, ZoneNode):
        return node
    if isinstance(node.first, ZoneNode) and node.first.id == zone_id:
        return node.second
    if isinstance(node.second, ZoneNode) and node.second.id == zone_id:
        return node.first
    node.first = _prune_zone(node.first, zone_id)
    node.second = _prune_zone(node.second, zone_id)
    return node
