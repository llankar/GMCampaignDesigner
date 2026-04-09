"""Serialization helpers for workspace layout state."""

from __future__ import annotations

from modules.scenarios.gm_screen2.state.layout_state import LayoutNode, LayoutState, PanelInstanceState, SplitNode, ZoneNode


def serialize_layout(layout: LayoutState) -> dict[str, object]:
    return {
        "root": _serialize_node(layout.root),
        "panel_instances": {
            panel_id: {
                "min_size": state.min_size,
                "visible": state.visible,
                "collapsed": state.collapsed,
            }
            for panel_id, state in layout.panel_instances.items()
        },
    }


def deserialize_layout(data: dict[str, object]) -> LayoutState:
    panel_map = {}
    for panel_id, state in dict(data.get("panel_instances") or {}).items():
        payload = dict(state or {})
        panel_map[str(panel_id)] = PanelInstanceState(
            panel_id=str(panel_id),
            min_size=int(payload.get("min_size") or 220),
            visible=bool(payload.get("visible", True)),
            collapsed=bool(payload.get("collapsed", False)),
        )
    return LayoutState(root=_deserialize_node(dict(data.get("root") or {})), panel_instances=panel_map)


def _serialize_node(node: LayoutNode) -> dict[str, object]:
    if isinstance(node, ZoneNode):
        return {
            "kind": "zone",
            "id": node.id,
            "panel_stack": list(node.panel_stack),
            "active_panel_id": node.active_panel_id,
        }
    return {
        "kind": "split",
        "id": node.id,
        "axis": node.axis,
        "ratio": node.ratio,
        "first": _serialize_node(node.first),
        "second": _serialize_node(node.second),
    }


def _deserialize_node(data: dict[str, object]) -> LayoutNode:
    if data.get("kind") == "split":
        return SplitNode(
            id=str(data.get("id") or "split"),
            axis=str(data.get("axis") or "horizontal"),
            ratio=float(data.get("ratio") or 0.5),
            first=_deserialize_node(dict(data.get("first") or {})),
            second=_deserialize_node(dict(data.get("second") or {})),
        )
    return ZoneNode(
        id=str(data.get("id") or "zone"),
        panel_stack=[str(item) for item in list(data.get("panel_stack") or [])],
        active_panel_id=(str(data.get("active_panel_id")) if data.get("active_panel_id") else None),
    )
