from __future__ import annotations

import copy
from typing import Dict, Optional


class FlowCanvasModel:
    """Pure data operations for the visual flow canvas."""

    def __init__(self, payload=None):
        self._payload = copy.deepcopy(payload or {"version": 1, "nodes": [], "links": []})

    @property
    def payload(self):
        return self._payload

    def set_payload(self, payload):
        self._payload = copy.deepcopy(payload or {"version": 1, "nodes": [], "links": []})

    def get_node(self, node_id: str) -> Optional[Dict]:
        node_key = str(node_id or "")
        return next((node for node in self._payload.get("nodes", []) if str(node.get("id") or "") == node_key), None)

    def get_link(self, link_id: str) -> Optional[Dict]:
        link_key = str(link_id or "")
        return next((link for link in self._payload.get("links", []) if str(link.get("id") or "") == link_key), None)

    def move_node(self, node_id: str, x: int, y: int) -> bool:
        node = self.get_node(node_id)
        if node is None:
            return False
        node["x"] = int(x)
        node["y"] = int(y)
        return True

    def remove_node(self, node_id: str) -> bool:
        before = len(self._payload.get("nodes", []))
        self._payload["nodes"] = [n for n in self._payload.get("nodes", []) if str(n.get("id") or "") != str(node_id or "")]
        self._payload["links"] = [
            l for l in self._payload.get("links", [])
            if str(l.get("source") or "") != str(node_id or "") and str(l.get("target") or "") != str(node_id or "")
        ]
        return len(self._payload["nodes"]) != before

    def remove_link(self, link_id: str) -> bool:
        before = len(self._payload.get("links", []))
        self._payload["links"] = [l for l in self._payload.get("links", []) if str(l.get("id") or "") != str(link_id or "")]
        return len(self._payload["links"]) != before

    def reorder_nodes(self, dragged_id: str, target_id: str, *, place_after: bool = False) -> bool:
        """Reorder visual presentation only.

        `scene_index` is intentionally a UI ordering field and must not be used to infer
        logical progression between scenes. Progression remains defined by explicit links.
        """
        nodes = self._payload.get("nodes", [])
        drag_key = str(dragged_id or "")
        target_key = str(target_id or "")
        if not drag_key or not target_key or drag_key == target_key:
            return False

        drag_index = next((idx for idx, node in enumerate(nodes) if str(node.get("id") or "") == drag_key), -1)
        target_index = next((idx for idx, node in enumerate(nodes) if str(node.get("id") or "") == target_key), -1)
        if drag_index < 0 or target_index < 0:
            return False

        node = nodes.pop(drag_index)
        if drag_index < target_index:
            target_index -= 1
        insert_at = target_index + (1 if place_after else 0)
        nodes.insert(max(0, min(insert_at, len(nodes))), node)
        for position, item in enumerate(nodes):
            item["scene_index"] = position
        return True

    @staticmethod
    def is_invalid_reorder_target(dragged_id: str, target_id: str, links) -> bool:
        drag_key = str(dragged_id or "")
        target_key = str(target_id or "")
        if not drag_key or not target_key or drag_key == target_key:
            return True

        children = {}
        for link in links or []:
            if not isinstance(link, dict):
                continue
            source = str(link.get("source") or "")
            target = str(link.get("target") or "")
            if source and target:
                children.setdefault(source, set()).add(target)

        stack = [drag_key]
        visited = set()
        while stack:
            current = stack.pop()
            if current in visited:
                continue
            visited.add(current)
            for child in children.get(current, ()):
                if child == target_key:
                    return True
                stack.append(child)
        return False
